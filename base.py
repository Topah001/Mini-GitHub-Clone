from http.server import BaseHTTPRequestHandler
from pathlib import Path
from contextlib import contextmanager
import hashlib,hmac,json,os,secrets,sqlite3,time
DB=Path(os.environ.get('APP_DB',Path(__file__).with_name('data')/'app.sqlite3'))
@contextmanager
def connect():
 DB.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
 try:
  yield c
  c.commit()
 except Exception:
  c.rollback()
  raise
 finally:c.close()
def init_common():
 with connect() as c:c.executescript('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,salt TEXT NOT NULL,created INTEGER NOT NULL);CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires INTEGER NOT NULL);')
def hash_password(password,salt=None):
 salt=salt or secrets.token_hex(16);return salt,hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),240000).hex()
def register_user(username,password):
 username=username.strip()
 if not 3<=len(username)<=32 or not username.replace('_','').replace('-','').isalnum():raise ValueError('Username must be 3–32 letters, digits, underscores, or hyphens.')
 if not 8<=len(password)<=128:raise ValueError('Password must be 8–128 characters.')
 salt,digest=hash_password(password)
 try:
  with connect() as c:cur=c.execute('INSERT INTO users(username,password,salt,created) VALUES(?,?,?,?)',(username,digest,salt,int(time.time())));return {'id':cur.lastrowid,'username':username}
 except sqlite3.IntegrityError:raise ValueError('That username is already registered.')
def verify_user(username,password):
 with connect() as c:row=c.execute('SELECT id,username,password,salt FROM users WHERE username=?',(username.strip(),)).fetchone()
 if not row or not hmac.compare_digest(hash_password(password,row['salt'])[1],row['password']):raise ValueError('Invalid username or password.')
 return {'id':row['id'],'username':row['username']}
def issue_session(uid):
 token=secrets.token_urlsafe(32)
 with connect() as c:c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,int(time.time())+604800))
 return token
def auth_user(h):
 token=next((p.strip().split('=',1)[1] for p in h.headers.get('Cookie','').split(';') if p.strip().startswith('session=')),'')
 if not token:return None
 key=hashlib.sha256(token.encode()).hexdigest()
 with connect() as c:
  row=c.execute('SELECT u.id,u.username,s.expires FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?',(key,)).fetchone()
  if row and row['expires']>int(time.time()):return {'id':row['id'],'username':row['username']}
  c.execute('DELETE FROM sessions WHERE token_hash=?',(key,))
def logout(h):
 token=next((p.strip().split('=',1)[1] for p in h.headers.get('Cookie','').split(';') if p.strip().startswith('session=')),'')
 with connect() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
class APIHandler(BaseHTTPRequestHandler):
 server_version='LocalDemo/1.0'
 def log_message(self,*args):pass
 def send_json(self,data,status=200,headers=None):
  b=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
  for k,v in (headers or {}).items():self.send_header(k,v)
  self.end_headers();self.wfile.write(b)
 def body(self):
  n=int(self.headers.get('Content-Length','0'))
  if n>65536:raise ValueError('Request is too large.')
  d=json.loads(self.rfile.read(n) or b'{}')
  if not isinstance(d,dict):raise ValueError('Expected a JSON object.')
  return d
 def do_GET(self):
  if self.path=='/api/me':self.send_json({'user':auth_user(self)});return
  if self.path.startswith('/api/'):
   try:self.api_get()
   except ValueError as e:self.send_json({'error':str(e)},400)
   except PermissionError as e:self.send_json({'error':str(e)},403)
   return
  name='index.html' if self.path in ('/','/index.html') else self.path.lstrip('/')
  if name not in ('index.html','style.css','app.js'):self.send_error(404);return
  b=Path(__file__).with_name(name).read_bytes();mime={'html':'text/html; charset=utf-8','css':'text/css; charset=utf-8','js':'text/javascript; charset=utf-8'}[name.rsplit('.',1)[1]]
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(b)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");self.end_headers();self.wfile.write(b)
 def do_POST(self):
  origin=self.headers.get('Origin')
  if origin and origin not in ('http://127.0.0.1:8000','http://localhost:8000'):self.send_json({'error':'Cross-origin request rejected.'},403);return
  try:
   d=self.body()
   if self.path in ('/api/register','/api/login'):
    user=register_user(str(d.get('username','')),str(d.get('password',''))) if self.path.endswith('register') else verify_user(str(d.get('username','')),str(d.get('password','')));token=issue_session(user['id']);self.send_json({'user':user},201 if self.path.endswith('register') else 200,{'Set-Cookie':f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=604800'});return
   if self.path=='/api/logout':logout(self);self.send_json({'ok':True},headers={'Set-Cookie':'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'});return
   self.api_post(d)
  except ValueError as e:self.send_json({'error':str(e)},400)
  except PermissionError as e:self.send_json({'error':str(e)},403)
  except sqlite3.IntegrityError:self.send_json({'error':'That record already exists.'},409)

