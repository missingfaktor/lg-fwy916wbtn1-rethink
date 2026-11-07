from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import json
import subprocess
import threading
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'skills/lg-fwy916wbtn1/scripts/control.mjs'

class ControlTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.ready=True;owner=self
        class Fake(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,data,code=200):
                self.send_response(code);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(data).encode())
            def do_GET(self):
                if self.path=='/washers':self.reply([{'id':'fake-washer'}])
                elif self.path.startswith('/status/'):
                    self.reply({'selection':{'programme':'wash-dry'},'start':{'enabled':owner.ready,'revision':'reviewed','reason':None if owner.ready else 'Arm Remote Start'}})
                else:self.reply({'programmes':[]})
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.calls.append((self.path,body,self.headers.get('X-Rethink-Action')))
                if self.path.startswith('/programme/'):
                    self.reply({'selection':body,'start':{'enabled':owner.ready,'revision':'reviewed','reason':None if owner.ready else 'Arm Remote Start'}})
                else:self.reply({'message':'Start command sent to fake transport'},202)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Fake)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def command(self,*args):return subprocess.run(['node',str(SCRIPT),*args,'--base',self.base],capture_output=True,text=True)
    def test_plan_prepares_cycle_but_never_calls_start(self):
        result=self.command('plan','--programme','wash-dry','--temperature','40','--spin','1400','--drying','cupboard')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.calls,[('/programme/fake-washer',{'programme':'wash-dry','temperatureC':40,'spinRpm':1400,'drying':'cupboard'},'programme')])
        self.assertFalse(json.loads(result.stdout)['applianceCommandSent'])
    def test_explicit_start_prepares_then_sends_reviewed_revision_to_fake(self):
        result=self.command('start','--programme','wash-dry')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual([x[0] for x in self.calls],['/programme/fake-washer','/start/fake-washer'])
        self.assertEqual(self.calls[-1][1],{'revision':'reviewed'})
        self.assertFalse(json.loads(result.stdout)['cycleConfirmed'])
    def test_unarmed_start_is_refused_without_any_start_post(self):
        self.ready=False
        result=self.command('start','--programme','wash-dry')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual([x[0] for x in self.calls],['/programme/fake-washer'])
    def test_status_makes_no_write_requests(self):
        result=self.command('status')
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(self.calls,[])
