# 嵌入式 C/C++ 编译与验证流程

## 构建环境发现

1. 查看目标模块和仓库根目录中的 `CMakePresets.json`、`CMakeLists.txt`、`Makefile`、`*.uvprojx`、`*.ewp`、`*.ccsproject`、`meson.build`、CI 配置和工具链文件。
2. 确定构建入口、目标名、工具链、Debug/Release 配置、单元测试入口、仿真命令和产物位置。
3. 先运行最小的未修改基线构建，记录首个错误。基线本身失败时区分存量失败和本次改动引入的问题，必要时在报告中明确存量问题。
4. 不安装工具、下载依赖或修改 `PATH`，除非用户明确授权。

## 构建目标

### CMake

优先使用预设，避免临时覆盖工具链：

```powershell
cmake --list-presets
cmake --preset <preset-name>
cmake --build --preset <build-preset-name>
ctest --preset <test-preset-name>
```

无预设时在专属构建目录中显式指定生成器、构建类型、工具链文件和选项。不要把工具链路径、芯片型号或环境差异硬编码进源码。

### Make 与厂商构建

```powershell
make -n <target>
make <target> -j
```

嵌入式 SDK 可能要求先设置厂商环境变量或执行顶层脚本；优先复用项目已有脚本和 CI 命令。执行前先用 `make -n` 或项目 dry-run 选项确认关键命令。

### IDE 工程

- IAR：优先使用项目自带构建脚本或 `iarbuild <project>.ewp -build <configuration>`。
- Keil MDK：使用项目指定命令或 `UV4 -b <project>.uvprojx -j0 -o <logfile>`，通过日志判断结果。
- STM32CubeIDE/CCS：优先使用生成后的 headless build 命令或 CI 脚本，不依赖交互式 GUI。

## 警告标准

### GCC/Clang 起始集

目标构建至少保持项目当前标准；验证第一方代码时可按项目基线启用：

```text
-std=<project-standard> -Wall -Wextra
-Werror=implicit -Werror=implicit-int -Werror=implicit-function-declaration
-Werror=return-type -Werror=switch -Werror=unused-result
-Werror=uninitialized -Werror=maybe-uninitialized
```

可移植模块或新模块可逐步引入：

```text
-Wshadow -Wconversion -Wsign-conversion -Wcast-align -Wstrict-prototypes
-Wmissing-prototypes -Wredundant-decls -Wvla -Wformat=2
```

`-Wconversion` 和 `-Wsign-conversion` 可能与既有代码或厂商头文件冲突，应先限定到新模块或第一方目标，再逐步扩大。

### 必须修复

- 未初始化、悬空指针、空指针解引用、越界和严格别名冲突。
- 隐式函数声明、返回类型缺失、`switch` 缺 default、格式字符串不匹配。
- 有符号/无符号、截断、精度丢失、移位越界和依赖实现定义的转换。
- 变量遮蔽、未使用结果、可变长度数组、未受限递归和未指定求值顺序。
- `volatile` 使用错误、对齐错误、缓存/DMA 一致性问题和对编译器扩展的隐式依赖。

### 告警处理

1. 复现并定位第一个告警；必要时查看预处理输出和实际编译命令。
2. 修复根因，包括宽度、所有权、初始化、接口契约或并发保护。
3. 无法避免的平台相关代码使用显式局部转换、静态断言或厂商 API，并写明依据。
4. 第三方库告警只隔离在库自己的编译选项或目录作用域；不改第三方源码，也不放宽第一方代码标准。
5. 不提交 `-w`、降低项目级警告、注释诊断、用 `(void)` 吞错误或修改测试期望来掩盖问题。

## 静态与动态分析

- GCC/Clang：可用 `-fanalyzer`、`clang-tidy` 或 `cppcheck`，只分析第一方目录，并为新增问题建立可复现阈值。
- 主机端测试：可移植逻辑使用 ASan/UBSan；测试构建的 sanitizer 配置不需要与目标机相同。
- 硬件相关路径：使用 HAL 桩、仿真器、指令集模拟或单元测试框架，覆盖边界值、错误返回、超时、溢出和并发场景。
- 长期运行检查包括内存泄漏、队列满、栈溢出、看门狗复位、缓冲回卷和低功耗转换。

示例：

```powershell
clang-tidy <files> -- -std=c17 -I<include>
cppcheck --enable=warning,style,performance,portability --inline-suppr <dirs>
```

Linux 进程或主机测试可按项目配置使用：

```powershell
cmake --preset <test-preset> -DCMAKE_C_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -g"
cmake --build --preset <test-build-preset>
ctest --preset <test-preset> --output-on-failure
```

目标机通常不适合直接运行 ASan/UBSan；仅在工具链和内存预算明确支持时启用。

## 体积、栈和映射分析

- 使用 `arm-none-eabi-size`、`nm --size-sort`、IAR/Keil map 报告确认 Flash、RAM、栈、堆和中断向量预算。
- 检查新增 `.bss`、`.data`、对象池、队列和 DMA 缓冲；确认链接脚本不会隐式侵占安全余量。
- 栈分析至少覆盖最深调用链、中断嵌套、浮点上下文、库调用和 RTOS 任务上下文。
- 工具支持时运行静态栈深度分析；否则在设计中记录推导方法、假设和实测方案。
- 优化等级、LTO、内联和调试信息变化后重新评估代码体积、时序和可调试性。

## 测试策略

1. 最小编译：只构建受影响模块或目标。
2. 相关测试：优先运行受影响的测试文件、过滤条件或标签。
3. 目标链接：完整固件或库目标必须链接成功。
4. 全量回归：改动涉及公共接口、启动流程、存储、并发或内存分配时运行完整测试集。
5. 硬件测试：区分可在仿真中验证和必须上板验证的内容；未经授权不烧录。

## 常见失败定位

- 缺符号：检查链接脚本、库路径、条件编译、命名修饰和 `extern "C"`。
- 重复符号：检查头文件定义、模板实例化、厂商库重复链接和弱符号覆盖。
- 布局变化：比较 map 文件，检查对齐、`pragma pack`、缓存别名和启动初始化段。
- 随机失败：优先怀疑未保护共享数据、ISR 安全、栈溢出、DMA 一致性、未初始化变量和时钟/电源时序。
- 优化相关差异：检查 `volatile`、严格别名、未定义行为、有符号溢出、断言被 `NDEBUG` 消除和内联假设。

## 完成门槛

- 与改动相关的目标可重复构建成功。
- 新代码没有强制警告清单中的问题，新增告警不进入提交。
- 相关单元测试或仿真测试通过；测试失败只允许因明确用例期望更新而变化。
- 公共接口、错误码、并发要求和构建说明同步更新。
- 汇报构建命令、测试命令、产物路径、剩余硬件验证项和风险。
