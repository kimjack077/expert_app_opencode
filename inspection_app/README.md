# 现场检查助手 - Flutter客户端

专家现场工作辅助系统的跨平台移动应用，使用 Flutter 开发，支持 Android 和 iOS。

## 功能特性

- **用户认证**：支持用户名密码登录，Token 自动刷新
- **任务管理**：查看检查任务列表，筛选不同状态的任务
- **任务详情**：查看任务详情，开始/完成任务
- **快速检查**：无需创建任务，直接进行现场快速检查
- **个人中心**：查看个人信息和统计数据

## 技术栈

- **框架**：Flutter 3.x
- **状态管理**：Riverpod + Provider
- **路由管理**：Go Router
- **网络请求**：Dio
- **本地存储**：Shared Preferences + Flutter Secure Storage
- **UI组件**：Material Design 3 + 自定义组件

## 项目结构

```
lib/
├── main.dart                 # 应用入口
├── models/                   # 数据模型
│   ├── user_model.dart
│   └── task_model.dart
├── screens/                  # 页面
│   ├── login_screen.dart
│   ├── main_screen.dart
│   ├── task_list_screen.dart
│   ├── task_detail_screen.dart
│   ├── quick_check_screen.dart
│   └── profile_screen.dart
├── services/                 # 服务层
│   └── api_service.dart
├── providers/                # 状态管理
│   └── auth_provider.dart
├── router/                   # 路由配置
│   └── app_router.dart
├── theme/                    # 主题配置
│   └── app_theme.dart
└── utils/                    # 工具类
    └── storage_util.dart
```

## 开发环境配置

### 前提条件

- Flutter SDK >= 3.0.0
- Dart SDK >= 3.0.0
- Android Studio / VS Code
- Android SDK (Android 5.0+)
- Xcode (iOS开发)

### 安装依赖

```bash
flutter pub get
```

### 运行应用

```bash
# 开发模式
flutter run

# 指定设备
flutter run -d <device_id>

# 发布模式
flutter run --release
```

### 构建应用

```bash
# Android APK
flutter build apk

# Android App Bundle
flutter build appbundle

# iOS
flutter build ios
```

## API 配置

修改 `lib/services/api_service.dart` 中的 `baseUrl`：

```dart
static const String baseUrl = 'http://your-api-server/api';
```

## 演示账号

- 用户名：admin
- 密码：admin123

## 截图

（待添加）

## 许可证

MIT License
