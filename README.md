# bili-3x-helper

一个 Windows 小工具：在哔哩哔哩 PC 客户端播放视频时，虚拟按住键盘右方向键，让播放器保持 3 倍速。

> 非官方工具，与哔哩哔哩无关联，仅供个人学习与方便使用。

## 功能

- **F8**：开启 / 停止 3x
- **F9**：隐藏 / 呼出窗口
- 只对 `哔哩哔哩.exe` 窗口生效，切换到其它软件会自动松开
- 工具窗口不抢焦点，拖动、点击不会中断加速
- 不修改 B站 客户端文件，只发送键盘事件

## 使用

1. 下载 Releases 中的 `bili-3x-helper.exe`。
2. 打开 B站视频，点一下画面让播放器获得键盘焦点。
3. 按 **F8**，或点击工具里的“开启 3x”。
4. 需要停止时再按一次 **F8**，或点击“停止 3x”。

工具窗口挡视线时可以按 **F9** 隐藏，隐藏后快捷键仍然有效。

## 依赖

| 依赖 | 类型 | 用途 | 打包后是否还需要 | 说明 |
|---|---|---|---|---|
| Python 3.14+ | 运行时 | 运行源码版 | 不需要 | exe 已内置 Python 运行时 |
| tkinter / Tcl-Tk 8.6 | GUI 库 | 工具窗口 | 已内置 | 随 exe 一起打包 |
| ctypes / ctypes.wintypes | 标准库 | 调用 Win32 API | 已内置 | 按键注入、窗口检测 |
| threading / queue / atexit / time / os / sys | 标准库 | 热键线程、消息队列、退出清理 | 已内置 | 无额外依赖 |
| Windows 10 / 11 x64 | 系统环境 | 运行平台 | 需要 | 使用 User32 / Kernel32 接口 |
| 哔哩哔哩 PC 客户端 | 外部程序 | 目标应用 | 需要 | 只对 `哔哩哔哩.exe` 窗口生效 |
| PyInstaller 6.x | 构建工具 | 打 exe | 不需要 | 仅构建时使用 |

运行时不联网，也不依赖第三方 pip 包。

## 从源码运行

```powershell
python bili_3x.pyw
```

需要 Python 3.10+，并带上 tkinter。

## 打包

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name bili-3x-helper bili_3x.pyw
```

生成的 exe 在 `dist\` 目录下。

## 说明

- 本项目不包含哔哩哔哩的图标、字体或其它资源。
- 请遵守哔哩哔哩的用户协议；因使用本工具产生的任何问题由使用者自行承担。
- 不提供任何形式的担保。
