"""
域名管理 API 路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core import get_db
from app.models import EmailDomain
from app.schemas import DomainCreate, DomainUpdate, DomainResponse, MessageResponse

router = APIRouter()


@router.get("", response_model=List[DomainResponse])
async def list_domains(db: AsyncSession = Depends(get_db)):
    """获取域名列表"""
    stmt = select(EmailDomain).order_by(EmailDomain.created_at.desc())
    result = await db.execute(stmt)
    domains = result.scalars().all()
    return domains


@router.post("", response_model=DomainResponse)
async def create_domain(
    data: DomainCreate,
    db: AsyncSession = Depends(get_db)
):
    """添加域名"""
    # 检查域名是否已存在
    stmt = select(EmailDomain).where(EmailDomain.domain == data.domain)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="域名已存在")
    
    domain = EmailDomain(
        domain=data.domain,
        cf_zone_id=data.cf_zone_id,
        usage_limit=data.usage_limit,
        note=data.note,
    )
    
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    
    return domain


@router.put("/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: int,
    data: DomainUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新域名"""
    stmt = select(EmailDomain).where(EmailDomain.id == domain_id)
    result = await db.execute(stmt)
    domain = result.scalar_one_or_none()
    
    if not domain:
        raise HTTPException(status_code=404, detail="域名不存在")
    
    if data.cf_zone_id is not None:
        domain.cf_zone_id = data.cf_zone_id
    if data.is_enabled is not None:
        domain.is_enabled = data.is_enabled
    if data.usage_limit is not None:
        domain.usage_limit = data.usage_limit
    if data.note is not None:
        domain.note = data.note
    
    await db.commit()
    await db.refresh(domain)
    
    return domain


@router.delete("/{domain_id}", response_model=MessageResponse)
async def delete_domain(domain_id: int, db: AsyncSession = Depends(get_db)):
    """删除域名"""
    stmt = select(EmailDomain).where(EmailDomain.id == domain_id)
    result = await db.execute(stmt)
    domain = result.scalar_one_or_none()
    
    if not domain:
        raise HTTPException(status_code=404, detail="域名不存在")
    
    await db.delete(domain)
    await db.commit()
    
    return MessageResponse(message=f"域名 {domain.domain} 已删除")


@router.post("/{domain_id}/toggle", response_model=DomainResponse)
async def toggle_domain(domain_id: int, db: AsyncSession = Depends(get_db)):
    """切换域名启用状态"""
    stmt = select(EmailDomain).where(EmailDomain.id == domain_id)
    result = await db.execute(stmt)
    domain = result.scalar_one_or_none()
    
    if not domain:
        raise HTTPException(status_code=404, detail="域名不存在")
    
    domain.is_enabled = not domain.is_enabled
    await db.commit()
    await db.refresh(domain)
    
    return domain


@router.post("/{domain_id}/test", response_model=MessageResponse)
async def test_domain(domain_id: int, db: AsyncSession = Depends(get_db)):
    """测试域名配置"""
    stmt = select(EmailDomain).where(EmailDomain.id == domain_id)
    result = await db.execute(stmt)
    domain = result.scalar_one_or_none()
    
    if not domain:
        raise HTTPException(status_code=404, detail="域名不存在")
    
    # TODO: 实际发送测试邮件并检查 KV 是否收到
    # 目前仅检查 Cloudflare KV 连接状态
    from app.services.cloudflare_kv import cf_kv_client
    
    if not cf_kv_client.is_configured:
        return MessageResponse(
            message="Cloudflare KV 未配置，请先在系统设置中配置",
            success=False
        )
    
    test_result = await cf_kv_client.test_connection()
    
    if test_result["success"]:
        return MessageResponse(message=f"域名 {domain.domain} KV 连接测试成功")
    else:
        return MessageResponse(
            message=f"测试失败: {test_result.get('error', '未知错误')}",
            success=False
        )
