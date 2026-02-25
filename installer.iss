; Inno Setup 安装脚本 - Windows ToolsPack
; 支持：管理员权限、开机自启、卸载清理

#define MyAppName "Windows ToolsPack"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "WindowsToolsPack"
#define MyAppExeName "WindowsToolsPack.exe"
#define MyAppURL "https://github.com/yourusername/WindowsToolsPack"

[Setup]
; 应用基本信息
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE
OutputDir=installer
OutputBaseFilename=WindowsToolsPack-Setup-v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

; 权限设置
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; 图标设置
SetupIconFile=assets\icons\icon.ico
UninstallDisplayIcon={app}\assets\icons\icon.ico

; 架构支持
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "开机自动启动"; GroupDescription: "其他选项:"; Flags: checkedonce

[Files]
Source: "dist\WindowsToolsPack.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icons\icon.ico"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\assets\icons\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\icons\icon.ico"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup; IconFilename: "{app}\assets\icons\icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 卸载前关闭正在运行的程序
Filename: "{cmd}"; Parameters: "/c taskkill /f /im {#MyAppExeName}"; Flags: runhidden

[Code]
// 检查程序是否正在运行
function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec('tasklist', '/FI "IMAGENAME eq {#MyAppExeName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := (ResultCode = 0);
  end;
end;

// 安装前检查
function InitializeSetup(): Boolean;
begin
  Result := True;
  if IsAppRunning() then
  begin
    if MsgBox('检测到 {#MyAppName} 正在运行。' + #13#10 + '是否关闭程序并继续安装？',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec('taskkill', '/f /im {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Sleep(1000);
      Result := True;
    end
    else
      Result := False;
  end;
end;

// 卸载前检查
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if IsAppRunning() then
  begin
    if MsgBox('检测到 {#MyAppName} 正在运行。' + #13#10 + '是否关闭程序并继续卸载？',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec('taskkill', '/f /im {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Sleep(1000);
      Result := True;
    end
    else
      Result := False;
  end;
end;
