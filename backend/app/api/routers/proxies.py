"""
代理管理 API 路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core import get_db
from app.core.config import settings
from app.models import ProxyNode
from app.schemas import ProxyNodeResponse, ProxyNodeUpdate, MessageResponse
from app.services.clash_manager import clash_manager
from app.services.proxy_pool import ProxyConfig
from pydantic import BaseModel
import logging
logger = logging.getLogger(__name__)

router = APIRouter()


class ProxyBatchToggleRequest(BaseModel):
    ids: List[int]
    is_enabled: bool


@router.get("", response_model=List[ProxyNodeResponse])
async def list_proxies(db: AsyncSession = Depends(get_db)):
    """获取代理节点列表 (合并数据库节点和内存中的外部节点)"""
    # 1. 获取数据库中的管理节点 (Clash 节点)
    stmt = select(ProxyNode).order_by(ProxyNode.name)
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())
    
    # 2. 将内存池中各代理节点的健康度、延迟、使用次数同步持久化到数据库
    from app.services.proxy_pool import proxy_pool
    from sqlalchemy import update
    
    # 提取所有带有 node_id 的内存态节点
    memory_updates = {}
    async with proxy_pool.lock:
        for p in proxy_pool.proxies:
            if p.node_id:
                memory_updates[p.node_id] = {
                    "is_healthy": p.is_healthy,
                    "latency": p.latency,
                    "usage_count": p.usage_count,
                    "is_enabled": p.is_enabled
                }
                
    if memory_updates:
        for db_node in nodes:
            stats = memory_updates.get(db_node.id)
            if stats:
                db_node.is_healthy = stats["is_healthy"]
                db_node.latency = stats["latency"]
                db_node.usage_count = stats["usage_count"]
                
                # 更新数据库
                await db.execute(
                    update(ProxyNode)
                    .where(ProxyNode.id == db_node.id)
                    .values(**stats)
                )
        await db.commit()
        
        # 重新获取，防止 DetachedInstanceError
        stmt = select(ProxyNode).order_by(ProxyNode.name)
        result = await db.execute(stmt)
        nodes = list(result.scalars().all())

    return nodes


@router.get("/pool-status")
async def get_proxy_pool_status():
    """获取代理池状态（含分组统计）"""
    from app.services.proxy_pool import proxy_pool
    async with proxy_pool.lock:
        group_stats = {}
        for p in proxy_pool.proxies:
            group = p.group or "default"
            stat = group_stats.setdefault(
                group,
                {"total": 0, "enabled": 0, "healthy": 0, "active": 0, "idle": 0}
            )
            stat["total"] += 1
            if p.is_enabled:
                stat["enabled"] += 1
            if p.is_healthy:
                stat["healthy"] += 1
            if f"{p.host}:{p.port}" in proxy_pool.active_proxies:
                stat["active"] += 1
            if p.is_enabled and p.is_healthy and f"{p.host}:{p.port}" not in proxy_pool.active_proxies:
                stat["idle"] += 1

        overall = {
            "total": len(proxy_pool.proxies),
            "enabled": sum(1 for p in proxy_pool.proxies if p.is_enabled),
            "healthy": sum(1 for p in proxy_pool.proxies if p.is_healthy),
            "active": len(proxy_pool.active_proxies),
            "idle": sum(
                1 for p in proxy_pool.proxies
                if p.is_healthy and p.is_enabled and f"{p.host}:{p.port}" not in proxy_pool.active_proxies
            ),
        }

    return {"overall": overall, "groups": group_stats}


@router.get("/pool-diagnostics")
async def get_proxy_pool_diagnostics():
    """获取代理池明细诊断信息"""
    from app.services.proxy_pool import proxy_pool
    async with proxy_pool.lock:
        active_keys = set(proxy_pool.active_proxies)
        key_counts = {}
        for p in proxy_pool.proxies:
            key = f"{p.host}:{p.port}"
            key_counts[key] = key_counts.get(key, 0) + 1

        items = []
        for p in proxy_pool.proxies:
            key = f"{p.host}:{p.port}"
            is_active = key in active_keys
            if not p.is_enabled:
                reason = "disabled"
            elif not p.is_healthy:
                reason = "unhealthy"
            elif is_active:
                reason = "active"
            else:
                reason = "idle"

            items.append({
                "name": p.name,
                "group": p.group,
                "host": p.host,
                "port": p.port,
                "key": key,
                "duplicate_count": key_counts.get(key, 1),
                "is_enabled": bool(p.is_enabled),
                "is_healthy": bool(p.is_healthy),
                "is_active": is_active,
                "reason": reason,
                "usage_count": int(p.usage_count or 0),
                "latency": p.latency,
                "region_tag": p.region_tag,
            })

        summary = {
            "total": len(proxy_pool.proxies),
            "enabled": sum(1 for p in proxy_pool.proxies if p.is_enabled),
            "healthy": sum(1 for p in proxy_pool.proxies if p.is_healthy),
            "active": len(active_keys),
            "idle": sum(
                1 for p in proxy_pool.proxies
                if p.is_healthy and p.is_enabled and f"{p.host}:{p.port}" not in active_keys
            ),
            "duplicates": sum(1 for k, c in key_counts.items() if c > 1),
        }

    return {"summary": summary, "items": items}


@router.post("/sync", response_model=MessageResponse)
async def sync_proxies(db: AsyncSession = Depends(get_db)):
    """从 Clash 同步节点"""
    from app.services.clash_manager import clash_manager
    try:
        clash_nodes = await clash_manager.get_proxy_group_nodes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clash API 错误: {e}")
    
    if not clash_nodes:
        raise HTTPException(status_code=404, detail=f"未找到 '{clash_manager.proxy_group}' 代理组或组内无节点")
    
    synced_count = 0
    new_count = 0
    
    for node in clash_nodes:
        stmt = select(ProxyNode).where(ProxyNode.name == node.name)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            await db.execute(
                update(ProxyNode)
                .where(ProxyNode.id == existing.id)
                .values(node_type=node.node_type)
            )
            synced_count += 1
        else:
            new_node = ProxyNode(
                name=node.name,
                node_type=node.node_type,
                source="clash"
            )
            db.add(new_node)
            new_count += 1
            
    # 清理 DB 中旧的、且不属于本次拉取范围内的 Clash 节点
    valid_names = [node.name for node in clash_nodes]
    from sqlalchemy import delete
    delete_stmt = delete(ProxyNode).where(
        (ProxyNode.source == "clash") | (ProxyNode.source == None),
        ProxyNode.name.not_in(valid_names)
    )
    delete_result = await db.execute(delete_stmt)
    deleted_count = delete_result.rowcount
    
    # 清理外部代理：检查外部代理文件，如果文件不存在/为空则清除所有外部节点
    ext_deleted = 0
    from pathlib import Path
    ext_path = settings.ext_proxy_file_path
    ext_file_exists = bool(ext_path) and Path(ext_path).exists()
    ext_file_has_content = False
    
    if ext_file_exists:
        try:
            from app.services.proxy_pool import proxy_pool
            await proxy_pool.load_from_file(clear_existing=True)
            valid_ext_keys = {p.unique_id for p in proxy_pool.proxies if p.group == "external"}
            ext_file_has_content = len(valid_ext_keys) > 0
            
            if ext_file_has_content:
                ext_stmt = select(ProxyNode).where(ProxyNode.source == "external")
                ext_nodes = list((await db.execute(ext_stmt)).scalars().all())
                for node in ext_nodes:
                    key = f"{node.host}:{node.port}:{getattr(node, 'username', '') or ''}:{getattr(node, 'password', '') or ''}"
                    if key not in valid_ext_keys:
                        await db.delete(node)
                        ext_deleted += 1
        except Exception as e:
            logger.warning(f"检查外部代理文件同步失败: {e}")
    
    if not ext_file_exists or not ext_file_has_content:
        # 文件不存在或为空，清除所有外部节点
        ext_del_stmt = delete(ProxyNode).where(ProxyNode.source == "external")
        ext_del_result = await db.execute(ext_del_stmt)
        ext_deleted = ext_del_result.rowcount
        if ext_deleted > 0:
            logger.info(f"外部代理文件不存在或为空，已清理 {ext_deleted} 个废弃的外部节点")
    
    await db.commit()
    
    # 同时加载到内存代理池（不再自动追加外部代理）
    from app.services.proxy_pool import proxy_pool
    await proxy_pool.load_from_clash()
    
    # 同步清理内存池中的废弃外部节点
    if ext_deleted > 0:
        async with proxy_pool.lock:
            proxy_pool.proxies = [p for p in proxy_pool.proxies if p.group != "external"]
    
    total_deleted = deleted_count + ext_deleted
    return MessageResponse(
        message=f"同步完成: 新增 {new_count} 个, 更新 {synced_count} 个, 清理废弃节点 {total_deleted} 个"
    )


@router.get("/clash-status")
async def get_clash_status():
    """检查 Clash 连接状态"""
    from app.services.clash_manager import clash_manager
    connected = await clash_manager.check_connection()
    current_node = None
    
    if connected:
        current_node = await clash_manager.get_current_node()
    
    return {
        "connected": connected,
        "current_node": current_node,
        "last_switch_error": clash_manager.last_switch_error
    }


@router.put("/{node_id}", response_model=ProxyNodeResponse)
async def update_proxy(
    node_id: int,
    data: ProxyNodeUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新节点信息"""
    stmt = select(ProxyNode).where(ProxyNode.id == node_id)
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    
    update_values = {}
    if data.region_tag is not None:
        update_values["region_tag"] = data.region_tag
    if data.is_enabled is not None:
        update_values["is_enabled"] = data.is_enabled
    if data.name is not None:
        update_values["name"] = data.name
    if data.node_type is not None:
        update_values["node_type"] = data.node_type
    if data.host is not None:
        update_values["host"] = data.host
    if data.port is not None:
        update_values["port"] = data.port
    if data.username is not None:
        update_values["username"] = data.username
    if data.password is not None:
        update_values["password"] = data.password
    if data.protocol is not None:
        update_values["protocol"] = data.protocol
    if data.source is not None:
        update_values["source"] = data.source

    if update_values:
        await db.execute(
            update(ProxyNode)
            .where(ProxyNode.id == node_id)
            .values(**update_values)
        )
        await db.commit()

    result = await db.execute(select(ProxyNode).where(ProxyNode.id == node_id))
    node = result.scalar_one_or_none()

    # 同步内存代理池状态
    if "is_enabled" in update_values:
        from app.services.proxy_pool import proxy_pool
        async with proxy_pool.lock:
            for p in proxy_pool.proxies:
                if getattr(p, "node_id", None) == node_id:
                    p.is_enabled = update_values["is_enabled"]
                    break

    return node


@router.post("/{node_id}/toggle", response_model=ProxyNodeResponse)
async def toggle_proxy(node_id: int, db: AsyncSession = Depends(get_db)):
    """切换节点启用状态"""
    stmt = select(ProxyNode).where(ProxyNode.id == node_id)
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    
    current_enabled = bool(node.is_enabled)
    await db.execute(
        update(ProxyNode)
        .where(ProxyNode.id == node_id)
        .values(is_enabled=(not current_enabled))
    )
    await db.commit()
    result = await db.execute(select(ProxyNode).where(ProxyNode.id == node_id))
    node = result.scalar_one_or_none()
    
    # 同步内存代理池状态
    from app.services.proxy_pool import proxy_pool
    async with proxy_pool.lock:
        for p in proxy_pool.proxies:
            if getattr(p, "node_id", None) == node_id:
                p.is_enabled = not current_enabled
                break
    
    return node


@router.post("/batch-toggle", response_model=MessageResponse)
async def batch_toggle_proxies(data: ProxyBatchToggleRequest, db: AsyncSession = Depends(get_db)):
    """批量启用/禁用代理节点"""
    if not data.ids:
        raise HTTPException(status_code=400, detail="ids cannot be empty")

    stmt = select(ProxyNode).where(ProxyNode.id.in_(data.ids))
    result = await db.execute(stmt)
    nodes = result.scalars().all()
    if not nodes:
        raise HTTPException(status_code=404, detail="nodes not found")

    await db.execute(
        update(ProxyNode)
        .where(ProxyNode.id.in_(data.ids))
        .values(is_enabled=data.is_enabled)
    )
    await db.commit()

    # 同步内存代理池状态
    from app.services.proxy_pool import proxy_pool
    async with proxy_pool.lock:
        id_set = set(data.ids)
        for p in proxy_pool.proxies:
            if p.node_id and p.node_id in id_set:
                p.is_enabled = data.is_enabled

    return MessageResponse(message=f"updated {len(nodes)} nodes")


@router.post("/test-latency", response_model=MessageResponse)
async def test_all_latency(db: AsyncSession = Depends(get_db)):
    """测试所有节点延迟及地理位置"""
    stmt = select(ProxyNode).where(ProxyNode.is_enabled == True)
    result = await db.execute(stmt)
    nodes = result.scalars().all()
    
    from datetime import datetime
    import asyncio
    from app.services.proxy_pool import proxy_pool, ProxyConfig
    
    tested_count = 0
    pool_proxies_to_test = []
    unmapped_clash_nodes = []
    
    # 1. 尝试将节点映射到内存池（无论是 External 还是 Clash 本地开启了端口的）
    async with proxy_pool.lock:
        for node in nodes:
            found_in_pool = None
            is_external = str(getattr(node, "source", "")) == "external"
            
            for p in proxy_pool.proxies:
                # 核心逻辑：如果是外部节点，我们需要在池里找到那个 host:port 一致的对象
                if is_external:
                    # 1. 优先完全一致匹配 (含 Source 或 Group 标识)
                    if p.name == node.name and (p.group == "external" or "ext-" in p.name):
                        found_in_pool = p
                        break
                    # 2. 兜底匹配：即便名称变了，只要物理出口(127.0.0.1)后的真实映射信息一致，就认为选中了该通道
                    if p.host == "127.0.0.1":
                         ext_key = f"{node.host}:{node.port}:{getattr(node, 'username', '') or ''}:{getattr(node, 'password', '') or ''}"
                         mapped_port = proxy_pool.external_port_map.get(ext_key)
                         if mapped_port and p.port == mapped_port:
                             found_in_pool = p
                             break
                elif not is_external and p.node_id == node.id:
                    found_in_pool = p
                    break
            
            if found_in_pool is None and is_external:
                logger.warning(
                    "External node missing pool mapping, skip direct test: %s",
                    f"{node.host}:{node.port}:{getattr(node, 'username', '') or ''}:{getattr(node, 'password', '') or ''}"
                )
            
            if found_in_pool:
                # 复制一份用于测试，免得锁环境并发污染
                pool_proxies_to_test.append(found_in_pool)
            else:
                unmapped_clash_nodes.append(node)

    logger.info(f"全网测速: 本地端口并发探测 {len(pool_proxies_to_test)} 个，纯 Clash 探测 {len(unmapped_clash_nodes)} 个")

    # 2. 对已映射本地端口的节点进行并发完整探测并同步 DB（validate_all_proxies 里自带 DB 更新）
    if pool_proxies_to_test:
         await proxy_pool.validate_all_proxies(pool_proxies_to_test)
         tested_count += len(pool_proxies_to_test)

    # 3. 对未能映射到本地端口的纯 Clash 节点使用 clash 原生延迟测试接口
    async def test_unmapped_clash_node(node: ProxyNode, sem: asyncio.Semaphore):
        async with sem:
            latency = await clash_manager.test_node_delay(str(node.name))
            is_healthy = latency is not None and latency < 3000
            
            # 使用基于名称的 fallback 由于没有真实的通过代理发送请求的能力
            region_tag = node.region_tag
            if is_healthy and (not region_tag or region_tag == "UN"):
                name_u = (node.name or "").upper()
                mapping = {
                    "HK": ["HK", "香港"], "SG": ["SG", "新加坡", "狮城"], "JP": ["JP", "日本", "东京", "大阪"],
                    "US": ["US", "美国", "洛杉矶", "圣何塞"], "KR": ["KR", "韩国", "首尔"],
                    "TW": ["TW", "台湾", "台北", "新北"], "GB": ["UK", "GB", "英国", "伦敦"],
                    "DE": ["DE", "德国", "法兰克福"], "FR": ["FR", "法国", "巴黎"],
                    "NL": ["NL", "荷兰"], "CA": ["CA", "加拿大"], "AU": ["AU", "澳洲", "澳大利亚"],
                    "ES": ["ES", "西班牙"], "IT": ["IT", "意大利"], "RU": ["RU", "俄罗斯"],
                    "IN": ["IN", "印度"], "BR": ["BR", "巴西"], "ZA": ["ZA", "南非"],
                    "TR": ["TR", "土耳其"], "MY": ["MY", "马来西亚"], "TH": ["TH", "泰国"],
                    "VN": ["VN", "越南"], "PH": ["PH", "菲律宾"], "ID": ["ID", "印尼", "印度尼西亚"],
                    "CH": ["CH", "瑞士"], "SE": ["SE", "瑞典"], "NO": ["NO", "挪威"],
                    "DK": ["DK", "丹麦"], "FI": ["FI", "芬兰"], "IE": ["IE", "爱尔兰"],
                    "AT": ["AT", "奥地利"], "PL": ["PL", "波兰"], "CZ": ["CZ", "捷克"],
                    "GR": ["GR", "希腊"], "PT": ["PT", "葡萄牙"], "AR": ["AR", "阿根廷"],
                    "CL": ["CL", "智利"], "MX": ["MX", "墨西哥"], "AE": ["AE", "阿联酋", "迪拜"],
                    "IL": ["IL", "以色列"], "SA": ["SA", "沙特"], "RO": ["RO", "罗马尼亚"]
                }
                for code, kws in mapping.items():
                    if any(kw.upper() in name_u for kw in kws):
                        region_tag = code
                        break

            # 即时单独更新此节点避免大事务造成失败
            try:
                # 在协程内部创建新的 session 提交
                from app.core.database import async_session_factory
                async with async_session_factory() as inner_db:
                    update_vals = {
                        "latency": latency if is_healthy else 9999,
                        "is_healthy": is_healthy,
                        "last_tested_at": datetime.utcnow(),
                    }
                    if region_tag and region_tag != "UN":
                        update_vals["region_tag"] = region_tag
                        
                    await inner_db.execute(
                        update(ProxyNode)
                        .where(ProxyNode.id == node.id)
                        .values(**update_vals)
                    )
                    await inner_db.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to update Clash node {node.name} directly: {e}")
                return False

    if unmapped_clash_nodes:
        sem = asyncio.Semaphore(10) # 限制基于 HTTP 的并发数为10
        tasks = [test_unmapped_clash_node(node, sem) for node in unmapped_clash_nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        tested_count += sum(1 for r in results if r is True)
    
    return MessageResponse(message=f"已测试 {tested_count} 个启用节点")


@router.post("/{node_id}/test-latency", response_model=ProxyNodeResponse)
async def test_node_latency(node_id: int, db: AsyncSession = Depends(get_db)):
    """测试单个节点延迟及地理位置"""
    stmt = select(ProxyNode).where(ProxyNode.id == node_id)
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
        
    from datetime import datetime
    from app.services.proxy_pool import proxy_pool, ProxyConfig
    import asyncio
    
    is_external = str(getattr(node, "source", "")) == "external"
    found_in_pool = None
    
    # 1. 在内存池中寻找是否存在该节点（打通了本地端口）
    async with proxy_pool.lock:
        for p in proxy_pool.proxies:
            if is_external:
                if p.name == node.name and (p.group == "external" or "ext-" in p.name):
                    found_in_pool = p
                    break
                if p.host == "127.0.0.1":
                     from app.services.proxy_pool_runner import pool_runner
                     if pool_runner.active_ports_info:
                         for p_info in pool_runner.active_ports_info:
                             if p_info["port"] == p.port:
                                 if p_info.get("original_host") == node.host and p_info.get("original_port") == node.port:
                                     found_in_pool = p
                                     break
                         if found_in_pool: break
            elif not is_external and p.node_id == node.id:
                found_in_pool = p
                break

    # 2. 对于外部节点，如果池里没有，就临时造一个用来单点测试
    if found_in_pool is None and is_external:
        found_in_pool = ProxyConfig(
            host=str(node.host),
            port=int(node.port),
            username=node.username,
            password=node.password,
            protocol=str(node.protocol or "socks5"),
            name=str(node.name or "external"),
            group="external",
            node_id=node.id,
        )

    # 3. 如果找到了合适的通道（External 或者被映射的 Clash节点），直接走网络真实探测
    if found_in_pool:
        await proxy_pool.validate_all_proxies([found_in_pool])
        # 此时数据库已经在 validate_all_proxies 中被更新，只需重新获取返回给前端即可
        await db.refresh(node)
    else:
        # 4. 如果是普通 Clash 节点且当前不在代理池中，走 Clash API 并尝试名称匹配
        latency = await clash_manager.test_node_delay(str(node.name))
        is_healthy = latency is not None and latency < 3000
        region_tag = node.region_tag
        
        if is_healthy and (not region_tag or region_tag == "UN"):
            name_u = (node.name or "").upper()
            mapping = {
                "HK": ["HK", "香港"], "SG": ["SG", "新加坡", "狮城"], "JP": ["JP", "日本", "东京", "大阪"],
                "US": ["US", "美国", "洛杉矶", "圣何塞"], "KR": ["KR", "韩国", "首尔"],
                "TW": ["TW", "台湾", "台北", "新北"], "GB": ["UK", "GB", "英国", "伦敦"],
                "DE": ["DE", "德国", "法兰克福"], "FR": ["FR", "法国", "巴黎"],
                "NL": ["NL", "荷兰"], "CA": ["CA", "加拿大"], "AU": ["AU", "澳洲", "澳大利亚"],
                "ES": ["ES", "西班牙"], "IT": ["IT", "意大利"], "RU": ["RU", "俄罗斯"],
                "IN": ["IN", "印度"], "BR": ["BR", "巴西"], "ZA": ["ZA", "南非"],
                "TR": ["TR", "土耳其"], "MY": ["MY", "马来西亚"], "TH": ["TH", "泰国"],
                "VN": ["VN", "越南"], "PH": ["PH", "菲律宾"], "ID": ["ID", "印尼", "印度尼西亚"],
                "CH": ["CH", "瑞士"], "SE": ["SE", "瑞典"], "NO": ["NO", "挪威"],
                "DK": ["DK", "丹麦"], "FI": ["FI", "芬兰"], "IE": ["IE", "爱尔兰"],
                "AT": ["AT", "奥地利"], "PL": ["PL", "波兰"], "CZ": ["CZ", "捷克"],
                "GR": ["GR", "希腊"], "PT": ["PT", "葡萄牙"], "AR": ["AR", "阿根廷"],
                "CL": ["CL", "智利"], "MX": ["MX", "墨西哥"], "AE": ["AE", "阿联酋", "迪拜"],
                "IL": ["IL", "以色列"], "SA": ["SA", "沙特"], "RO": ["RO", "罗马尼亚"]
            }
            for code, kws in mapping.items():
                if any(kw.upper() in name_u for kw in kws):
                    region_tag = code
                    break
                    
        update_vals = {
            "latency": latency if is_healthy else 9999,
            "is_healthy": is_healthy,
            "last_tested_at": datetime.utcnow(),
        }
        if region_tag and region_tag != "UN":
            update_vals["region_tag"] = region_tag
            
        await db.execute(
            update(ProxyNode)
            .where(ProxyNode.id == node.id)
            .values(**update_vals)
        )
        await db.commit()
        await db.refresh(node)

    return node

@router.get("/pool/status")
async def get_pool_status():
    """获取内存代理池状态"""
    from app.services.proxy_pool import proxy_pool
    return proxy_pool.get_status()

@router.get("/pool/debug")
async def get_pool_debug():
    """获取内存代理池的详细内容，用于排查 BUG"""
    from app.services.proxy_pool import proxy_pool
    return [
        {
            "name": p.name,
            "host": p.host,
            "port": p.port,
            "is_enabled": p.is_enabled,
            "group": p.group,
            "node_id": getattr(p, "node_id", None)
        }
        for p in proxy_pool.proxies
    ]

@router.post("/pool/reload", response_model=MessageResponse)
async def reload_pool(db: AsyncSession = Depends(get_db)):
    """
    根据当前在数据库中启用的节点 ("is_enabled"=True)，
    重新生成并启动本地代理池 (Mihomo 实例)。
    """
    from app.services.proxy_pool import proxy_pool
    # 0. 强制同步外部代理配置，清理不再存在于文件中的旧节点
    await proxy_pool.load_from_file(clear_existing=True)
    ext_proxies = [p for p in proxy_pool.proxies if p.group == "external"]
    ext_keys_in_file = {p.unique_id for p in ext_proxies}
    
    existing_ext_stmt = select(ProxyNode).where(ProxyNode.source == "external")
    existing_ext = list((await db.execute(existing_ext_stmt)).scalars().all())
    
    # 删除已经在外部文件中失效的旧数据库节点
    for db_node in existing_ext:
        key = f"{db_node.host}:{db_node.port}:{getattr(db_node, 'username', '') or ''}:{getattr(db_node, 'password', '') or ''}"
        if key not in ext_keys_in_file:
            await db.delete(db_node)
            
    # 新增或更新从文件中读取的外部节点
    existing_ext_map = {f"{n.host}:{n.port}:{getattr(n, 'username', '') or ''}:{getattr(n, 'password', '') or ''}": n for n in existing_ext}
    for p in ext_proxies:
        key = p.unique_id
        if key in existing_ext_map:
            # 更新协议等关键元数据
            node = existing_ext_map[key]
            if node.protocol != p.protocol:
                node.protocol = p.protocol
        else:
            node = ProxyNode(
                name=p.name,
                node_type=(p.protocol or "http").upper(),
                host=p.host,
                port=p.port,
                username=p.username,
                password=p.password,
                protocol=p.protocol,
                region_tag=p.region_tag,
                is_enabled=p.is_enabled,
                is_healthy=p.is_healthy,
                latency=p.latency,
                usage_count=p.usage_count,
                source="external",
            )
            db.add(node)
    await db.commit()

    # 1. 获取所有启用的节点信息 (此时包含了最新的外部代理)
    stmt = select(ProxyNode).where(ProxyNode.is_enabled == True)
    result = await db.execute(stmt)
    enabled_nodes = result.scalars().all()
    
    enabled_clash_names = [str(getattr(n, "name", "")) for n in enabled_nodes if str(getattr(n, "source", "")) != "external"]
    enabled_external = [n for n in enabled_nodes if str(getattr(n, "source", "")) == "external"]
    
    # 2. 停止旧的池并启动新的池
    from app.services.proxy_pool_runner import pool_runner
    pool_runner.stop()
    
    external_for_runner = []
    for p in enabled_external:
        external_for_runner.append({
            "name": p.name or f"ext-{p.host}:{p.port}",
            "type": str(p.protocol or "socks5").lower(),
            "protocol": str(p.protocol or "socks5").lower(), # 显式传递 protocol 供 runner 识别
            "server": str(p.host),
            "port": int(p.port),
            "username": str(p.username or ""),
            "password": str(p.password or ""),
            "skip-cert-verify": True,
            "udp": False # 住宅代理强制关闭 UDP
        })
        
    active_ports_metadata = []
    if enabled_clash_names or external_for_runner:
        # 启动新的实例，传入允许的节点列表和外部直连节点配置
        active_ports_metadata = await pool_runner.start(
            allowed_proxy_names=enabled_clash_names,
            external_proxies=external_for_runner
        )
        
        if not active_ports_metadata:
            logger.warning("启动本地代理池未返回端口信息，可能是节点加载失败或全部被过滤")
    else:
        logger.info("无启用的节点，跳过本地代理池启动")
        
    # 3. 构造传递给内存池的数据 (包含数据库中的 ID 和 使用次数)
    ports_to_load = []

    # Create a normalized map for lenient matching
    def normalize_name(name: str) -> str:
        if not name:
            return ""
        return name.strip()

    node_map_normalized = {normalize_name(str(getattr(n, "name", ""))): n for n in enabled_nodes}

    for item in active_ports_metadata:
        node_name = item.get("name")
        normalized_name = normalize_name(str(node_name) if node_name else "")

        node = node_map_normalized.get(normalized_name)
        if node:
            logger.info(f"MATCH FOUND (lenient): '{node_name}' -> node_id {node.id}")
            ports_to_load.append({
                "port": item["port"],
                "node_name": node.name,
                "node_id": node.id,
                "usage_count": node.usage_count or 0,
                "region_tag": node.region_tag,
                "group": "external" if str(getattr(node, "source", "")) == "external" else node.region_tag,
                "original_host": item.get("original_host"),
                "original_port": item.get("original_port"),
                "original_username": item.get("original_username"),
                "original_password": item.get("original_password"),
                "original_protocol": item.get("original_protocol"),
                "is_external": item.get("is_external")
            })
        else:
            logger.warning(f"NO MATCH for runner name: '{node_name}' (normalized: '{normalized_name}')")
            ports_to_load.append(item)
    
    # 4. 更新内存中的代理池管理器
    # preserve_external=False 意味着清理所有旧的存量对象，仅仅把 127.0.0.1 映射注入内存池
    count = await proxy_pool.load_from_local_ports(ports_to_load, preserve_external=False)
    
    logger.info(f"Memory pool load result: {count} ports loaded.")
    
    return MessageResponse(message="代理池已重载成功（包含 Clash 和 External）")
