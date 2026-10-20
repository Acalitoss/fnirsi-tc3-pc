"""Build a standalone Windows application with the verified firmware bundled."""
from pathlib import Path
import argparse,sys,shutil,hashlib,json
from build_patch import build

root=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--firmware',type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!='win32':raise SystemExit('Build this executable on Windows x64.')
    build(args.firmware,root/'build')
    import PyInstaller.__main__
    name='RetroSaver-TC3-PC-v1.0-Windows-x64'
    image=root/'build/DSO-TC3_V0.3_USB_EXPERIMENTAL.s19'
    bundle_image=root/'build/DSO-TC3-PC-v1.0-patched.s19'
    shutil.copyfile(image,bundle_image)
    PyInstaller.__main__.run(['--onefile','--windowed','--noconfirm','--name',name,
        '--paths',str(root),'--distpath',str(root/'dist'),'--workpath',str(root/'build/pyinstaller'),
        '--specpath',str(root/'build'),
        '--add-data',f'{bundle_image}:firmware','--add-data',f'{root/"assets"}:assets',
        '--hidden-import','serial.tools.list_ports_windows',str(root/'scripts/windows_entry.py')])
    release=root/'dist';shutil.copyfile(image,release/'DSO-TC3-PC-v1.0-patched.s19')
    hashes=[]
    for path in [release/f'{name}.exe',release/'DSO-TC3-PC-v1.0-patched.s19']:
        hashes.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}')
    (release/'SHA256SUMS.txt').write_text('\n'.join(hashes)+'\n',encoding='utf-8')
