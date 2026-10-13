import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,base
class Tests(unittest.TestCase):
 def setUp(self):base.DB=Path(__file__).resolve().parents[1]/'data'/'test.sqlite3';base.DB.parent.mkdir(exist_ok=True);base.DB.unlink(missing_ok=True);app.init_db();self.u=base.register_user('coder','sample-pass-123');self.r=app.create_repo(self.u['id'],'hello-world','Demo')
 def tearDown(self):base.DB.unlink(missing_ok=True)
 def test_safe_text_file_stored_and_read(self):
  app.save_file(self.u['id'],self.r,'src/main.py','print("hello")');self.assertEqual(app.repository(self.r)['files'][0]['content'],'print("hello")')
 def test_path_traversal_rejected(self):
  for p in ('../escape.py','/root.py','src/../../x.py','C:\\oops.py'):
   with self.subTest(path=p),self.assertRaises(ValueError):app.save_file(self.u['id'],self.r,p,'x')
 def test_non_owner_cannot_write(self):
  other=base.register_user('other','sample-pass-456')
  with self.assertRaises(PermissionError):app.save_file(other['id'],self.r,'file.py','x')
 def test_extension_and_size_limits(self):
  with self.assertRaises(ValueError):app.save_file(self.u['id'],self.r,'payload.exe','x')
  with self.assertRaises(ValueError):app.save_file(self.u['id'],self.r,'large.txt','x'*50001)
if __name__=='__main__':unittest.main()

