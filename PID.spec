# -*- mode: python -*-

block_cipher = None


a = Analysis(['main_mat_anim.py'],
             pathex=['D:\\Python\\Signal'],
             binaries=[],
             datas=[('./image0/Icon.ico', './image0'),
                    ('./image0/hand.png', './image0')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='PID',
          debug=False,
          strip=False,
          upx=True,
          console=False, icon='./image0/Icon.ico')
