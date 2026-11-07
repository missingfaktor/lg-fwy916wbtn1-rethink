#!/usr/bin/env node
// status/catalogue/plan are passive with respect to the appliance. Only start actuates.
import { parseArgs } from 'node:util'
const {values,positionals}=parseArgs({allowPositionals:true,options:{
    base:{type:'string',default:'http://127.0.0.1:44401'},device:{type:'string'},
    programme:{type:'string'},temperature:{type:'string'},spin:{type:'string'},drying:{type:'string'},
}})
const action=positionals[0]??'status'
const allowed=['status','catalogue','plan','start']
if(!allowed.includes(action)||positionals.length>1)throw new Error('Use status, catalogue, plan or start.')
const base=new URL(values.base)
if(!['http:','https:'].includes(base.protocol))throw new Error('Use an HTTP(S) management URL.')
async function request(path,body,kind){
    const options=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Rethink-Action':kind},body:JSON.stringify(body)}
    const response=await fetch(new URL(path,base),options)
    const data=await response.json()
    if(!response.ok)throw new Error(data.error??'The local washer request failed.')
    return data
}
function selection(){
    if(!values.programme)throw new Error('Specify --programme when setting a cycle.')
    const out={programme:values.programme}
    if(values.temperature!==undefined){out.temperatureC=values.temperature==='auto'?null:values.temperature==='cold'?0:Number(values.temperature)}
    if(values.spin!==undefined){out.spinRpm=values.spin==='auto'?null:values.spin==='none'?0:Number(values.spin)}
    if(values.drying!==undefined)out.drying=values.drying
    for(const k of ['temperatureC','spinRpm'])if(k in out&&out[k]!==null&&!Number.isFinite(out[k]))throw new Error('Use numeric temperature/spin, cold/none, or auto.')
    return out
}
try{
    if(action==='catalogue'){console.log(JSON.stringify(await request('/programmes'),null,2));process.exit(0)}
    let id=values.device
    if(!id){const devices=await request('/washers');if(devices.length!==1)throw new Error('Specify --device when there is not exactly one connected washer.');id=devices[0].id}
    if(action==='status'){console.log(JSON.stringify(await request('/status/'+encodeURIComponent(id)),null,2));process.exit(0)}
    if(!values.programme&&['temperature','spin','drying'].some(k=>values[k]!==undefined))throw new Error('Include --programme when changing cycle settings.')
    const plan=action==='plan'||values.programme?
        await request('/programme/'+encodeURIComponent(id),selection(),'programme'):
        await request('/status/'+encodeURIComponent(id))
    if(action==='plan'){console.log(JSON.stringify({...plan,applianceCommandSent:false},null,2));process.exit(0)}
    if(!plan.start?.enabled)throw new Error(plan.start?.reason??'The washer is not ready to start.')
    const result=await request('/start/'+encodeURIComponent(id),{revision:plan.start.revision},'start')
    console.log(JSON.stringify({selection:plan.selection,...result,applianceCommandSent:true,cycleConfirmed:false},null,2))
}catch(error){console.error(JSON.stringify({error:error.message}));process.exitCode=1}
