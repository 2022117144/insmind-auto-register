; insMind Desktop — 代理配置自定义安装页面
; 在选安装路径后弹出，让用户填代理地址

!include nsDialogs.nsh

Var ProxyHost
Var ProxyPort
Var HostField
Var PortField

; ── 代理配置页面 ──
Page custom proxyPage proxyPageLeave

Function proxyPage
  nsDialogs::Create 1018
  Pop $0

  ${NSD_CreateLabel} 0 0 100% 12u "HTTP 代理地址："
  Pop $1
  ${NSD_CreateText} 0 14u 100% 12u "127.0.0.1"
  Pop $HostField

  ${NSD_CreateLabel} 0 32u 100% 12u "HTTP 代理端口："
  Pop $1
  ${NSD_CreateText} 0 46u 100% 12u "7897"
  Pop $PortField

  ${NSD_CreateLabel} 0 62u 100% 10u "不需要代理则保持默认，可留空。"
  Pop $1

  nsDialogs::Show
FunctionEnd

Function proxyPageLeave
  ${NSD_GetText} $HostField $ProxyHost
  ${NSD_GetText} $PortField $ProxyPort
FunctionEnd

; ── 安装完成后保存配置 ──
!macro customInstall
  ; 保存代理配置到安装目录
  FileOpen $0 "$INSTDIR\proxy-config.json" w
  FileWrite $0 '{"host":"$ProxyHost","port":"$ProxyPort"}'
  FileClose $0
!macroend