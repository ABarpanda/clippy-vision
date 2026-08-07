; Clippy Vision keeps running in the tray after the window is closed, so a
; new install/upgrade can hit a locked .exe/.asar and silently fail to
; overwrite it, leaving the old process running with stale code. Force-close
; any running instance before install and uninstall proceed.

!macro customInit
  nsExec::Exec 'taskkill /F /IM "Clippy Vision.exe" /T'
!macroend

!macro customUnInit
  nsExec::Exec 'taskkill /F /IM "Clippy Vision.exe" /T'
!macroend
