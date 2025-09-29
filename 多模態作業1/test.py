# 快速驗證 RAW 大小（在你的資料夾內跑）
import os
for name in ["lena.raw","goldhill.raw","peppers.raw"]:
    print(name, os.path.getsize(name))  # 應該都印 262144
