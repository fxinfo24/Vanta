# Desktop & Mobile Applications

Vanta provides both desktop and mobile interfaces for comprehensive social media analysis across all supported platforms.

## Desktop Application
Vanta Desktop is a PyQt5-based application that provides a native desktop interface for social media analysis with advanced visualization capabilities.

### Features
- **Multi-platform Analysis**: Support for all 10+ social platforms
- **Progress**: polling-based task status (no WebSockets implemented)
- **Advanced Visualizations**: Interactive charts and graphs
- **Bulk Processing**: Analyze multiple profiles simultaneously
- **Export Capabilities**: PDF, JSON, CSV, and image exports
- **Offline Mode**: Continue working without internet connection
- **Team Integration**: not implemented (enterprise modules are unwired)

### Installation
```bash
# Desktop app is included in main installation
python3 bin/run.py --desktop
```

### System Requirements
- Python 3.9+
- PyQt5 (automatically installed)
- 4GB RAM minimum, 8GB recommended
- 1GB disk space for data and exports

## Mobile Applications  
Vanta Mobile is built with React Native and Expo, providing cross-platform iOS and Android applications with touch-optimized interfaces for on-the-go analysis.

### Features
- **Touch-Optimized Interface**: Designed for mobile interaction
- **Cross-Platform**: Single codebase for iOS and Android
- **Real-time Sync**: Automatic sync with web and desktop
- **Offline Capability**: View cached results without internet
- **Push Notifications**: Get notified when analysis completes
- **Mobile Analytics**: Optimized charts for small screens
- **Quick Analysis**: Simplified interface for common tasks

### Installation

#### Development
```bash
cd mobile
npm install
npx expo start

# For iOS simulator
npx expo start --ios

# For Android emulator  
npx expo start --android
```

#### Production
- iOS: Available on App Store (pending deployment)
- Android: Available on Google Play (pending deployment)
- Web: Progressive Web App at app.vanta.com

### Mobile-Specific Features
- **Quick Scan**: Fast profile analysis with essential metrics
- **Share Integration**: Share analysis results via native sharing
- **Camera Integration**: Scan profile QR codes (where available)
- **Voice Commands**: Voice-activated analysis requests
- **Gesture Navigation**: Swipe-based navigation between analyses

### System Requirements
- iOS 12.0+ or Android 8.0+
- 2GB RAM minimum
- 500MB disk space for app and cache
- Internet connection for real-time analysis

## Platform Comparison

| Feature | Web App | Desktop App | Mobile App |
|---------|---------|-------------|------------|
| **Platforms** | All 10+ | All 10+ | All 10+ |
| **Real-time** | ✅ | ✅ | ✅ |
| **Bulk Analysis** | ✅ | ✅ | Limited |
| **Advanced Charts** | ✅ | ✅ | Simplified |
| **Export Options** | All formats | All formats | Share/Cloud |
| **Offline Mode** | Limited | ✅ | View only |
| **Team Features** | ✅ | ✅ | ✅ |
| **Notifications** | Browser | System | Push |

## Getting Started

### Desktop Quick Start
1. Launch: `python3 bin/run.py --desktop`
2. Enter platform and username
3. Configure analysis options
4. Start analysis and view real-time progress
5. Export results in preferred format

### Mobile Quick Start
1. Download from app store (or use Expo)
2. Sign in with Vanta account
3. Tap "New Analysis"
4. Select platform and enter username
5. View results and share insights

## Advanced Features

### Desktop Advanced
- **Batch Processing**: CSV upload for multiple profiles
- **Custom Reports**: Template-based report generation
- **API Integration**: Direct access to Vanta API
- **Plugin System**: Extensible analysis modules
- **Database Export**: Direct database connectivity

### Mobile Advanced
- **Geolocation**: Location-based analysis insights
- **AR Integration**: Augmented reality profile overlay
- **Widget Support**: Home screen analysis widgets
- **Shortcuts**: Siri/Google Assistant integration
- **Background Sync**: Automatic analysis updates

## Support and Documentation

- **Desktop Help**: Press F1 or Help → Documentation
- **Mobile Support**: Shake device for support options
- **Online Docs**: docs.vanta.com
- **Video Tutorials**: Available in app help sections
- **Community**: community.vanta.com
