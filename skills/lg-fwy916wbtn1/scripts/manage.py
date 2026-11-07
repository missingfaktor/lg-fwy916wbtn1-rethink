#!/usr/bin/env python3
"""Manage software and passive services. This CLI has no appliance Start action."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

ASSETS=Path(__file__).resolve().parent.parent/'assets'
UPSTREAM=json.loads((ASSETS/'upstream.json').read_text())
TESTS=['tests/cloud/devices/Y_V8_F___W.B32QEUK.test.ts','tests/cloud/devices/aabb_device.test.ts',
       'tests/management/washer-start.test.ts','tests/management/device-monitor.test.ts']

def run(args,**kwargs):
    return subprocess.run(args,check=True,text=True,**kwargs)

def patch_hash():
    h=hashlib.sha256(json.dumps(UPSTREAM,sort_keys=True).encode())
    for name in UPSTREAM['patches']:h.update((ASSETS/name).read_bytes())
    return h.hexdigest()

def source(workspace):
    state=json.loads((workspace/'installation.json').read_text())
    result=Path(state['source'])
    if state['patch_sha256']!=patch_hash():
        raise SystemExit('The installed skill changed. Run prepare and verify before configuring or starting services.')
    marker=json.loads((result/'.fwy-package.json').read_text())
    diff=run(['git','diff','--no-ext-diff','--no-textconv','--no-color','--binary','HEAD'],cwd=result,capture_output=True).stdout
    if hashlib.sha256(diff.encode()).hexdigest()!=marker['diff_sha256']:
        raise SystemExit('The prepared source has local changes. Preserve them rather than silently rebuilding over them.')
    return result

def prepare(workspace):
    os.umask(0o077)
    workspace.mkdir(parents=True,exist_ok=True)
    digest=patch_hash()
    target=workspace/'sources'/(UPSTREAM['revision'][:12]+'-'+digest[:12])
    marker=target/'.fwy-package.json'
    if not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True)
        run(['git','clone','--no-checkout',UPSTREAM['repository'],str(target)])
        run(['git','checkout','--detach',UPSTREAM['revision']],cwd=target)
        for patch in UPSTREAM['patches']:
            run(['git','apply','--check',str(ASSETS/patch)],cwd=target)
            run(['git','apply',str(ASSETS/patch)],cwd=target)
        run(['git','add','-N','--','cloud/devices/Y_V8_F___W.B32QEUK.ts',
             'tests/cloud/devices/Y_V8_F___W.B32QEUK.test.ts','tests/helpers/fwy916wbtn1-fixtures.ts',
             'tests/management/washer-start.test.ts','html/washer.html'],cwd=target)
        diff=run(['git','diff','--no-ext-diff','--no-textconv','--no-color','--binary','HEAD'],cwd=target,capture_output=True).stdout
        marker.write_text(json.dumps({'diff_sha256':hashlib.sha256(diff.encode()).hexdigest()}))
    elif not marker.exists():
        raise SystemExit(f'An incomplete or unrelated checkout already exists at {target}; inspect it instead of overwriting it.')
    diff=run(['git','diff','--no-ext-diff','--no-textconv','--no-color','--binary','HEAD'],cwd=target,capture_output=True).stdout
    if hashlib.sha256(diff.encode()).hexdigest()!=json.loads(marker.read_text())['diff_sha256']:
        raise SystemExit('The prepared source has local changes. Preserve them and use a new workspace for this package version.')
    state={'upstream_revision':UPSTREAM['revision'],'patch_sha256':digest,'source':str(target)}
    (workspace/'installation.json').write_text(json.dumps(state,indent=2)+'\n')
    print('Prepared source:',target)

def verify(workspace):
    checkout=source(workspace)
    # No application is started here: the HTTP tests bind an ephemeral loopback port
    # and all their appliance transports are in-memory fakes.
    run(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],cwd=checkout)
    run(['npm','run','check'],cwd=checkout)
    env={**os.environ,'ESBK_DISABLE_CACHE':'1'}
    run(['node','--import','tsx','--test',*TESTS],cwd=checkout,env=env)
    run(['npm','run','build'],cwd=checkout)
    (workspace/'verified.json').write_text(json.dumps({'patch_sha256':patch_hash()})+'\n')

def configure(workspace,bind_address,hostname,management_port):
    os.umask(0o077)
    checkout=source(workspace)
    old_path=workspace/'network.json'
    if old_path.exists():
        old=json.loads(old_path.read_text())
        bind_address=bind_address or old['bind_address']
        hostname=hostname or old['hostname']
        management_port=management_port or old['management_port']
    if not bind_address or not hostname:
        raise SystemExit('Specify --bind-address and --hostname on the first configure run.')
    address=ipaddress.ip_address(bind_address)
    if address.version!=4 or address.is_unspecified or address.is_multicast or address.is_loopback or not address.is_private:
        raise SystemExit('Use a specific private IPv4 address assigned to this server.')
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',hostname) or hostname.lower().endswith('.local'):
        raise SystemExit('Use a DNS hostname, not an mDNS .local name.')
    try:ipaddress.ip_address(hostname)
    except ValueError:pass
    else:raise SystemExit('The hostname must be a DNS name, not an IP address.')
    port=management_port or 44401
    if not 1024<=port<=65535:raise SystemExit('Management port must be between 1024 and 65535.')
    data=workspace/'data';data.mkdir(mode=0o700,exist_ok=True)
    config=data/'config.json'
    if config.exists():
        current=json.loads(config.read_text())
        if current.get('hostname')!=hostname:
            raise SystemExit('The saved hostname differs. Preserve the existing certificates and review re-pairing before changing it.')
    else:
        config.write_text(json.dumps({'hostname':hostname,
            'homeassistant':{'mqtt_url':'mqtt://mqtt:1883','discovery_prefix':'homeassistant','rethink_prefix':'rethink','mqtt_user':'','mqtt_pass':''},
            'ca_key_file':'ca.key','ca_cert_file':'ca.cert','https_port':443,'mqtts_port':8883,
            'thinq1_https_port':{},'thinq1_port':{},'management_port':44401,
            'log':['status','incoming','outgoing','HTTPS']},indent=2)+'\n')
    (workspace/'mosquitto.conf').write_text('listener 1883\nallow_anonymous true\npersistence false\nlog_dest stdout\n')
    dockerfile=checkout/'Dockerfile.fwy916wbtn1'
    dockerfile.write_text('FROM '+UPSTREAM['image']+'\nCOPY dist/ /app/dist/\n')
    (checkout/'Dockerfile.fwy916wbtn1.dockerignore').write_text('**\n!dist/\n!dist/**\n')
    # JSON is valid YAML and avoids shell interpolation of paths or passwords.
    compose={'name':'lg-fwy916wbtn1','services':{
        'mqtt':{'image':'eclipse-mosquitto@sha256:75d6662dee52c947dc9dd9c29f1d8d7ffef78ddaf38001caa09755681e8bbc98',
            'volumes':['./mosquitto.conf:/mosquitto/config/mosquitto.conf:ro'],'restart':'no'},
        'rethink':{'image':'lg-fwy916wbtn1:'+patch_hash()[:12],
            'build':{'context':str(checkout).replace('$','$$'),'dockerfile':'Dockerfile.fwy916wbtn1'},
            'volumes':['./data:/app/data'],'ports':[f'{bind_address}:443:443',f'{bind_address}:8883:8883',f'127.0.0.1:{port}:44401'],
            'depends_on':['mqtt'],'restart':'no'}}}
    (workspace/'compose.yaml').write_text(json.dumps(compose,indent=2)+'\n')
    old_path.write_text(json.dumps({'bind_address':bind_address,'hostname':hostname,'management_port':port},indent=2)+'\n')
    print(f'Configured passive services. Washer page: http://127.0.0.1:{port}/washer')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','verify','configure','up','down','status'])
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--bind-address');p.add_argument('--hostname');p.add_argument('--management-port',type=int)
    p.add_argument('--docker-context',help='Choose the engine explicitly; needed for native Linux Wi-Fi setups.')
    args=p.parse_args();workspace=args.workspace.expanduser().resolve()
    if args.command=='prepare':prepare(workspace)
    elif args.command=='verify':verify(workspace)
    elif args.command=='configure':configure(workspace,args.bind_address,args.hostname,args.management_port)
    elif args.command in ['up','down']:
        source(workspace)
        if args.command=='up':
            verified=json.loads((workspace/'verified.json').read_text())
            if verified['patch_sha256']!=patch_hash():raise SystemExit('Run verify for the current package before starting its server.')
        docker=['docker']+(['--context',args.docker_context] if args.docker_context else [])
        run([*docker,'compose','-f',str(workspace/'compose.yaml'),*(['up','--build','-d'] if args.command=='up' else ['down'])],cwd=workspace)
    else:
        port=json.loads((workspace/'network.json').read_text())['management_port']
        base=f'http://127.0.0.1:{port}'
        with urllib.request.urlopen(base+'/washers',timeout=5) as r:devices=json.load(r)
        for device in devices:
            with urllib.request.urlopen(base+'/status/'+device['id'],timeout=5) as r:print(json.dumps(json.load(r),indent=2))

if __name__=='__main__':main()
