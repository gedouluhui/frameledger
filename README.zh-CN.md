# FrameLedger

**时间戳是一项声明，需要对应的帧证据。**

[在线交互演示](https://gedouluhui.github.io/frameledger/) · [在线篡改示例](https://gedouluhui.github.io/frameledger/tampered.html) · [English](README.md) · [本地示例](docs/index.html)

面向视频多模态数据制作：按照明确的时间原点和策略抽帧，再重新解码原视频，检查落盘图片、PTS、索引和清单是否一致。不是视频编辑器、模型评测榜或更快的解码器。

## 一键真实演示

```sh
git clone https://github.com/gedouluhui/frameledger.git
cd frameledger
python -m pip install .
frameledger demo --out demo-output
```

打开 `demo-output/index.html`。程序实际编码自制可变帧率视频，再执行抽帧和两次重新解码核验。`valid/index.html` 是正常对照，`tampered/index.html` 是故意篡改 PTS 的反例；原视频、PNG 和清单都可检查。没有下载用户素材或模型权重。

```sh
frameledger sample video.mkv --times 0,0.14,0.16 --policy nearest --origin first-frame --out samples
frameledger audit video.mkv samples/manifest.json --out verification
```

`first-frame` 以第一张实际解码帧为相对时间原点；`media` 使用媒体 PTS 时间坐标。`nearest` 选最近 PTS，平局取更早帧；`previous` 取不晚于请求的最后一帧。请求必须在首尾实际 PTS 之间，不用平均 FPS 猜时间，也不猜最后一帧显示多久。

## 证据与边界

清单记录源文件摘要、流索引、整数 PTS、有理 timebase、时间原点、策略和图像摘要。审计会重新解码；报告把声明值、源帧观察和 PNG 实测分开，图片不匹配时不会把那张图片冠为已验证源帧。

退出码 `0` 表示成功导出或通过核验，须同时读取 status；`1` 表示发现不一致；`2` 表示输入无效、无法完成或版本不可比较。抽帧成功不等于已经审计。预算中断的核验报告为 `incomplete`，没有已验证样本。

首版只做本地普通文件、CPU RGB24 和原始解码方向，不证明音画同步、HDR 色彩、显示旋转、GPU 或浏览器逐帧定位。UNC／远程映射盘／符号链接与重解析点、嵌套媒体读取会被拒绝。它不是恶意编解码器沙箱；完整预算和日志捕获约束见英文说明。

能够拒绝 FFmpeg 报告的截断错误，不等于能知道一个已经合法裁短或重编码的视频原来有多长。哈希证明一致性，不是数字签名。输出目录必须新建，报告内有缩略图和文件名，分享前注意自己的数据隐私。

## 验证状态

已进行首次独立代码审查，并按发现补充真实视频、截断、篡改、时间算术和来源归属的回归检查。**修复后的独立复审仍未完成**，原因是审查服务额度耗尽；不将维护者复验称作独立批准。当前是明确范围的早期版本，尚无外部真实用户验证。

自有代码与演示视频为 MIT。PyAV／FFmpeg、NumPy、Pillow 保留各自实际发行版本的许可证；源码仓不捆绑第三方独立编解码二进制或 Python 环境。
