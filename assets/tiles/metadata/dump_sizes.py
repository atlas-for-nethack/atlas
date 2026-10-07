"""Expand the pinned NetHack MON table through the C preprocessor/compiler.

Canonical art includes deferred/obsolete/conditional entries, so enable all
#if 0 blocks and CHARON/MAIL_STRUCTURES for this metadata-only dump.
"""
import json,subprocess,hashlib,re,tempfile
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parents[2]
source=root/'vendor/NetHack-5.0.0/include/monsters.h'
original=source.read_text();expanded=re.sub(r'^#if 0\b','#if 1',original,flags=re.M)
temporary=tempfile.TemporaryDirectory(prefix='atlas-size-metadata-')
build=Path(temporary.name)
(build/'expanded-monsters.h').write_text(expanded)
c='''#include <stdio.h>
#define CHARON
#define MAIL_STRUCTURES
#define NAM(n) n
#define NAMS(m,f,n) n
#define SIZ(w,n,s,z) #z
#define MON(nam,sym,lvl,gen,atk,siz,mr1,mr2,f1,f2,f3,d,col,bn) {#bn,nam,#sym,siz,#f1,#f2}
struct item {const char *symbol,*name,*class,*size,*f1,*f2;};
static struct item items[]={
#include "expanded-monsters.h"
};
int main(void){for(unsigned long i=0;i<sizeof(items)/sizeof(items[0]);i++) printf("%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n",items[i].symbol,items[i].name,items[i].class,items[i].size,items[i].f1,items[i].f2);return 0;}
'''
(build/'dump_sizes.c').write_text(c)
subprocess.run(['cc',str(build/'dump_sizes.c'),'-o',str(build/'dump-sizes')],check=True)
lines=subprocess.check_output([str(build/'dump-sizes')],text=True).splitlines()
records=[dict(zip(['symbol','name','class','size','flags1','flags2'],line.split('\t'))) for line in lines]
(here/'upstream-sizes.json').write_text(json.dumps({'source':'vendor/NetHack-5.0.0/include/monsters.h','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'conditional_policy':'Enabled all #if 0 blocks, CHARON and MAIL_STRUCTURES for canonical artwork coverage only. No engine files or gameplay changed.','monsters':records},indent=2)+'\n')
print('dump records',len(records));print('\n'.join(f'{i}: {r["name"]} {r["symbol"]} {r["size"]} {r["class"]}' for i,r in enumerate(records)))
temporary.cleanup()
