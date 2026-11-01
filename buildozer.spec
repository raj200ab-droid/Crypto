[app]
title = Crypto Signal Scanner Pro
package.name = cryptoscanner
package.domain = org.cryptoscanner
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,plyer,certifi,openssl,sqlite3
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,POST_NOTIFICATIONS
android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = v2024.01.21
p4a.bootstrap = sdl2

[buildozer]
log_level = 1
warn_on_root = 1
