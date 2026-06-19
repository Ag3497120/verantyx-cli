# VR Bridge PoC: Mac CLI Automation for Windows Guest OS
# 
# 目的: GUIを行き来する無駄を排除し、Macのターミナルから一発で
# Windows VM上のMSVCコンパイラをSSH経由で叩き、ドライバを自動デプロイする。

VM_USER = Administrator
VM_HOST = windows-vm.local
VM_DIR  = Z:\\driver

# SSHでWindows VMのコマンドプロンプトまたはPowerShellを呼び出してコンパイルする
build-driver:
	@echo "=> [Mac CLI] SSH経由で Windows VM に接続し、MSVCでドライバをコンパイルします..."
	ssh $(VM_USER)@$(VM_HOST) "cd $(VM_DIR) && msbuild Driver.sln /p:Configuration=Release /p:Platform=ARM64"
	@echo "=> [Mac CLI] コンパイル完了。"

# コンパイル済みのドライバ（.dll / .inf）をSteamVRのドライバディレクトリにデプロイまたはシステム登録する
deploy-driver:
	@echo "=> [Mac CLI] SSH経由で Windows VM のシステムにドライバを登録します..."
	# SteamVR のカスタムドライバお作法として、マニフェストファイルを自動生成する
	ssh $(VM_USER)@$(VM_HOST) "powershell -Command \"$$Manifest = @{ alwaysRegistered = $$true; name = 'verantyx'; resourceRoot = ''; driverRoot = ''; driver_displays = @() }; $$Manifest | ConvertTo-Json | Out-File -Encoding utf8 $(VM_DIR)\\Release\\driver.vrdrivermanifest\""
	@echo "=> [Mac CLI] driver.vrdrivermanifest の生成完了"

register-driver:
	@echo "=> [Mac CLI] vrpathreg を使用して SteamVR に Verantyx ドライバを登録します..."
	# Windows側の SteamVR インストールパスにある vrpathreg.exe を叩いて Z:\driver\Release を登録
	ssh $(VM_USER)@$(VM_HOST) "& 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\SteamVR\\bin\\win64\\vrpathreg.exe' adddriver $(VM_DIR)\\Release"
	@echo "=> [Mac CLI] ドライバ登録完了。"

# Mac側で共有メモリマッピングのためのダミーテストクライアントをビルド
build-mac-mock:
	@echo "=> [Mac CLI] Mac側でモック通信用のバイナリをビルドします..."
	# ここにClangでのモックビルド処理を記述
	
# 一発で全て実行する
run: build-driver deploy-driver register-driver
	@echo "=> [Mac CLI] Windows VM 上で SteamVR を再起動してドライバを読み込ませます..."
	ssh $(VM_USER)@$(VM_HOST) "taskkill /F /IM vrserver.exe ; start steam://rungameid/250820"

# =========================================================
# 【変態的ハック】 Macローカルでの完全クロスコンパイル (LLVM/Clang-cl)
# ※ Windows SDKが手元にある場合のみ実行可能
# =========================================================
cross-compile-mac:
	@echo "=> [Mac CLI] M1/M2 Mac フルパワーで Windows ARM64 向けバイナリをクロスコンパイルします..."
	# clang-cl --target=aarch64-pc-windows-msvc /LD driver_verantyx.cpp /link /OUT:driver_verantyx.dll
	@echo "=> [Mac CLI] 生成された dll は VirtioFS 経由で瞬時にWindowsへ同期されます。"
