#!/usr/bin/env node
import { parseArgs } from 'node:util'
import { mkdirSync,openSync,writeSync,closeSync } from 'node:fs'
import { dirname } from 'node:path'
const {values}=parseArgs({options:{base:{type:'string',default:'http://127.0.0.1:44401'},device:{type:'string'},output:{type:'string'},seconds:{type:'string',default:'60'}}})
if(!values.output)throw new Error('Specify --output in a private runtime directory; existing files are never overwritten.')
const seconds=Number(values.seconds)
if(!Number.isFinite(seconds)||seconds<1||seconds>600)throw new Error('Use a duration between 1 and 600 seconds.')
const base=new URL(values.base);if(!['http:','https:'].includes(base.protocol))throw new Error('Use an HTTP(S) management URL.')
let id=values.device
if(!id){const devices=await(await fetch(new URL('/washers',base))).json();if(devices.length!==1)throw new Error('Specify --device when there is not exactly one matching washer.');id=devices[0].id}
mkdirSync(dirname(values.output),{recursive:true,mode:0o700})
const fd=openSync(values.output,'wx',0o600)
const url=new URL('/device',base);url.protocol=base.protocol==='https:'?'wss:':'ws:';url.searchParams.set('id',id)
const ws=new WebSocket(url)
let done=false
function finish(){if(done)return;done=true;clearTimeout(timer);ws.close();closeSync(fd)}
const timer=setTimeout(finish,seconds*1000)
ws.onmessage=event=>{if(!done)writeSync(fd,JSON.stringify({at:new Date().toISOString(),...JSON.parse(event.data)})+'\n')}
ws.onclose=finish;ws.onerror=()=>{process.exitCode=1;finish()}
process.on('SIGINT',finish);process.on('SIGTERM',finish)
// Deliberately no WebSocket.send(): capture can never inject a packet.
