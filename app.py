import re
from http.server import ThreadingHTTPServer
from base import APIHandler,connect,init_common,auth_user
NAME=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,38}$');ALLOWED={'txt','md','py','js','html','css','json','yml','yaml','toml','sh','java','c','cpp','go','rs'}
def init_db():
 init_common()
 with connect() as c:c.executescript('CREATE TABLE IF NOT EXISTS repositories(id INTEGER PRIMARY KEY,owner INTEGER NOT NULL REFERENCES users(id),name TEXT NOT NULL,description TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,name)); CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY,repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,path TEXT NOT NULL,content TEXT NOT NULL,updated INTEGER NOT NULL,UNIQUE(repo_id,path));')
def validate_name(name):
 name=name.strip()
 if not NAME.fullmatch(name):raise ValueError('Use 1–39 letters, digits, hyphens, or underscores; start with a letter or digit.')
 return name
def validate_path(path):
 path=path.strip().replace('\\','/')
 if not path or len(path)>180 or path.startswith('/') or '\x00' in path:raise ValueError('Invalid file path.')
 parts=path.split('/')
 if any(p in ('','.','..') or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',p) for p in parts):raise ValueError('Path segments may contain only letters, digits, dot, underscore, and hyphen; traversal is forbidden.')
 ext=parts[-1].rsplit('.',1)[-1].lower() if '.' in parts[-1] else ''
 if parts[-1].lower() in ('.env','secrets.txt','id_rsa') or ext not in ALLOWED:raise ValueError('Only safe text/source file extensions are supported.')
 return '/'.join(parts)
def create_repo(owner,name,description=''):
 name=validate_name(name);description=description.strip()
 if len(description)>300:raise ValueError('Description must be 300 characters or fewer.')
 with connect() as c:cur=c.execute("INSERT INTO repositories(owner,name,description,created) VALUES(?,?,?,strftime('%s','now'))",(owner,name,description));return cur.lastrowid
def save_file(owner,rid,path,content):
 path=validate_path(path)
 if not isinstance(content,str) or len(content)>50000:raise ValueError('File must be text and no larger than 50 KB.')
 try:content.encode('utf-8')
 except UnicodeEncodeError:raise ValueError('File must be valid UTF-8 text.')
 with connect() as c:
  if not c.execute('SELECT 1 FROM repositories WHERE id=? AND owner=?',(rid,owner)).fetchone():raise PermissionError('Repository not found or not owned by you.')
  c.execute('INSERT INTO files(repo_id,path,content,updated) VALUES(?,?,?,strftime(\'%s\',\'now\')) ON CONFLICT(repo_id,path) DO UPDATE SET content=excluded.content,updated=excluded.updated',(rid,path,content))
def repository(rid):
 with connect() as c:
  row=c.execute('SELECT r.id,r.name,r.description,r.created,u.username owner FROM repositories r JOIN users u ON u.id=r.owner WHERE r.id=?',(rid,)).fetchone()
  if not row:raise ValueError('Repository not found.')
  d=dict(row);d['files']=[dict(f) for f in c.execute('SELECT path,content,updated FROM files WHERE repo_id=? ORDER BY path',(rid,))];return d
class Handler(APIHandler):
 def api_get(self):
  u=auth_user(self)
  if self.path=='/api/repos':
   with connect() as c:rows=c.execute('SELECT r.id,r.name,r.description,r.created,u.username owner FROM repositories r JOIN users u ON u.id=r.owner ORDER BY r.created DESC').fetchall()
   self.send_json({'repos':[dict(r) for r in rows],'user':u});return
  if self.path.startswith('/api/repos/'):
   try:rid=int(self.path.split('/')[3])
   except (IndexError,ValueError):raise ValueError('Invalid repository.')
   self.send_json({'repo':repository(rid)});return
  self.send_json({'error':'Not found.'},404)
 def api_post(self,d):
  u=auth_user(self)
  if not u:self.send_json({'error':'Sign in first.'},401);return
  if self.path=='/api/repos':self.send_json({'id':create_repo(u['id'],str(d.get('name','')),str(d.get('description','')))},201);return
  if self.path=='/api/files':
   try:rid=int(d.get('repo_id'))
   except (TypeError,ValueError):raise ValueError('Invalid repository.')
   save_file(u['id'],rid,str(d.get('path','')),d.get('content'));self.send_json({'ok':True},201);return
  self.send_json({'error':'Not found.'},404)
def main():
 init_db();print('Mini GitHub running at http://127.0.0.1:8000',flush=True);ThreadingHTTPServer(('127.0.0.1',8000),Handler).serve_forever()
if __name__=='__main__':main()
