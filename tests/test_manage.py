import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'skills/lg-fwy916wbtn1/scripts/manage.py'
spec=importlib.util.spec_from_file_location('fwy_manage',SCRIPT)
manage=importlib.util.module_from_spec(spec);spec.loader.exec_module(manage)

class ConfigurationTests(unittest.TestCase):
    def test_configuration_keeps_private_data_across_source_updates(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);checkout=root/'source';checkout.mkdir()
            with patch.object(manage,'source',return_value=checkout):
                manage.configure(root,'192.168.50.10','rethink.lan',44401)
                key=root/'data/ca.key';key.write_text('local-only-test-key')
                before=(root/'data/config.json').read_bytes()
                manage.configure(root,None,None,None)
                self.assertEqual(key.read_text(),'local-only-test-key')
                self.assertEqual((root/'data/config.json').read_bytes(),before)
                compose=json.loads((root/'compose.yaml').read_text())
                self.assertIn('127.0.0.1:44401:44401',compose['services']['rethink']['ports'])
                self.assertNotIn('ports',compose['services']['mqtt'])
                self.assertEqual((root/'data').stat().st_mode & 0o777,0o700)
                with self.assertRaises(SystemExit):manage.configure(root,None,'new-host.lan',None)
                self.assertEqual((root/'data/config.json').read_bytes(),before)

    def test_invalid_bind_and_mdns_are_refused_before_writing_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);checkout=root/'source';checkout.mkdir()
            with patch.object(manage,'source',return_value=checkout):
                for address,host in [('0.0.0.0','rethink.lan'),('192.168.50.10','rethink.local'),('192.168.50.10','192.168.50.10')]:
                    with self.assertRaises(SystemExit):manage.configure(root,address,host,44401)
                self.assertFalse((root/'data/config.json').exists())

    def test_command_line_has_no_start_action(self):
        with tempfile.TemporaryDirectory() as temp:
            result=subprocess.run([sys.executable,str(SCRIPT),'start','--workspace',temp],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('invalid choice',result.stderr)
            self.assertFalse((Path(temp)/'installation.json').exists())

if __name__=='__main__':unittest.main()
