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

退出码 `0` 表示成功导出或通过核验，须同时读取 status；`1` 表示发现不一致；`2` 表示输入无效、无法完成或版本不可比较。抽帧成功不等于已经审计。预算中断的核验报告为 `incomplete`，没有已验证样本。工具/解码器版本不同只使像素等价不可判定；像素格式或方向声明错误无论版本是否可比都确认判为失败，已确认失败不会被版本不确定降级。

首版只做本地普通文件、CPU RGB24 和原始解码方向，不证明音画同步、HDR 色彩、显示旋转、GPU 或浏览器逐帧定位。UNC／远程映射盘／符号链接与重解析点、嵌套媒体读取会被拒绝。它不是恶意编解码器沙箱；完整预算和日志捕获约束见英文说明。

能够拒绝 FFmpeg 报告的截断错误，不等于能知道一个已经合法裁短或重编码的视频原来有多长。哈希证明一致性，不是数字签名。输出目录必须新建，报告内有缩略图和文件名，分享前注意自己的数据隐私。

## 验证状态

已进行首次独立代码审查；独立复审确认部分修复，并发现四项遗留缺口：混合分隔符 UNC 仍触达驱动器查询、已确认的元数据失败被版本不可比掩盖、报告发布不具备事务性、origin 与请求域矛盾以裸异常逃逸。0.1.1 针对这些缺口补了回归测试；源码包现已带测试辅助、变异脚本和演示页，并附源码包→wheel→全新环境安装验证器。**对 0.1.1 的全新独立复审仍未完成**；不将维护者复验称作独立批准。当前是明确范围的早期版本，尚无外部真实用户验证。

自有代码与演示视频为 MIT。PyAV／FFmpeg、NumPy、Pillow 保留各自实际发行版本的许可证；源码仓不捆绑第三方独立编解码二进制或 Python 环境。

## 快速开始与支持状态

### 问题
在显式时间契约下导出帧，并通过重新解码源文件审计，从而保留精确的帧采样证据。

### 安装
```sh
python -m pip install .
```

### 成功命令
```sh
frameledger demo --out demo-output
```
预期：自生成 VFR 视频产生通过的 valid 审计和检测到篡改的审计；退出码 0。

### 故意失败命令
```sh
frameledger audit demo-output/synthetic-vfr.mkv demo-output/samples/tampered-manifest.json --out tampered-audit
```
预期：故意修改的 PTS 被报告为不匹配；退出码 1。

### 证据与覆盖边界
证据使用手写有理数选择 oracle、真实自生成视频、可用时独立的 ffprobe 观察、PNG/manifest 篡改、截断拒绝、日志恢复和精确分数往返。它证明所提供文件和所记录工具下的一致性，不证明录制完整性或跨版本解码器相等。

### 支持状态
版本 0.1.2 支持 Python 3.11+、PyAV 和本地 FFmpeg/ffprobe。0.1.1 的修复已有针对性回归测试，但新的独立复审和外部真实验证仍待完成。维护为尽力而为，不提供 SLA。

### 限制
输出为原始解码方向的 CPU RGB24。不证明音频同步、HDR/色彩保真、旋转感知呈现、GPU 行为、浏览器精确 seek 或跨版本解码器相等。该工具不是针对恶意编解码器输入的操作系统安全沙箱。
