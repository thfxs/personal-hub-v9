#!/usr/bin/env python3
"""Install 1.2 safe static subpages into an EXISTING Web build, without replacing its app.

Dry run by default, strictly refuses to overwrite conflicting assets. Does NOT update SW.
"""
from pathlib import Path
import argparse,hashlib,shutil,sys
SOURCE=Path(__file__).resolve().parents[1]/'web'
COPY=['bridge-launch.html','bridge-launch.js','bridge-launch.css',
      'safety/safety.html','safety/safety.css','safety/safety-ui.js',
      'safety/guard-core.js','safety/guard-auto.js',
      'diag/v9-check.html','diag/v9-check.js']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def integrate(target,apply=False):
 target=Path(target).expanduser().resolve()
 if not (target/'index.html').is_file():raise ValueError('没有 index.html：需要现有 Web 根目录')
 src_index=(target/'index.html').read_text(encoding='utf-8')
 if src_index.count('</body>')!=1:raise ValueError('index.html </body> 不唯一，拒绝自动编辑')
 if 'guard-core.js' in src_index or 'guard-auto.js' in src_index:
  if not ('./safety/guard-core.js' in src_index and './safety/guard-auto.js' in src_index):
   raise ValueError('发现现有保护模块引用，请人工核对，禁止盲目重装')
  revised=src_index
 else:
  revised=src_index.replace('</body>','<script src="./safety/guard-core.js"></script>\n<script src="./safety/guard-auto.js"></script>\n</body>')
 conflicts=[str(target/rel) for rel in COPY if (target/rel).exists() and sha(target/rel)!=sha(SOURCE/rel)]
 if conflicts:raise ValueError('文件冲突，未修改：'+', '.join(conflicts))
 print('目标：',target)
 print('保留原有 app.js / styles.css / sw.js / manifest / Android 包名与签名')
 print('新增安全模块入口：',revised!=src_index)
 print('新增或校验文件：',len(COPY),'个')
 print('快捷指令独立页：',target/'bridge-launch.html')
 print('0.8/0.6-0.8 自身已存在的业务逻辑不作修改；独立 PC bridge 不复制到公开目录')
 if not apply:
  print('[DRY RUN] 未改变任何文件。添加 --apply 才执行。')
  return
 # Require no preexisting rollback collision, write index only after all static copies succeed.
 bak=target/'.personal_hub_12_before'
 if (target/'index.html').read_bytes()!=src_index.encode('utf-8'):raise ValueError('应用在集成过程中发生变化，请重试')
 if not bak.exists():bak.mkdir()
 bakfile=bak/'index.html'
 if not bakfile.exists():shutil.copy2(target/'index.html',bakfile)
 for rel in COPY:
  dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists():shutil.copy2(SOURCE/rel,dest)
 if src_index!=revised:
  temp=target/'.index.html.12.tmp';temp.write_text(revised,encoding='utf-8');temp.replace(target/'index.html')
 print('[PASS] 已安装静态入口与资源；如原 SW 有白名单，请核对离线清单（未自动改 SW）。')
 print('[NOTE] 主页面未自动增加快捷指令图标，可手动访问 ./bridge-launch.html')

def main():
 ap=argparse.ArgumentParser(description='安全加装 1.2 模块；默认只检查，不修改')
 ap.add_argument('--web-root',type=Path,required=True);ap.add_argument('--apply',action='store_true')
 a=ap.parse_args()
 try:integrate(a.web_root,a.apply);return 0
 except Exception as e:print('[FAIL]',e);return 2
if __name__=='__main__':sys.exit(main())
