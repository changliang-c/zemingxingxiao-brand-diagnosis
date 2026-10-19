(function(global){
  'use strict';
  const protocol=new Set(['schema_version','case_id','submission_id','case_token','parent_submission_id','version','record_type']);
  const dropped=new Set(['brand','brand_name','company','company_name','business_name','person','person_name','customer_name','customer_id','name','contact','email','phone','mobile','address','exact_location','latitude','longitude','id_card','identity_number','source_ip','ip','raw_conversation','transcript','品牌','品牌名','公司名','姓名','负责人','客户明细','地址','电话','邮箱','身份证']);
  function scrub(value,terms,depth=0){
    if(depth>14) throw Error('记录层级过深');
    if(Array.isArray(value)) return value.map(x=>scrub(x,terms,depth+1));
    if(value&&typeof value==='object') return Object.fromEntries(Object.entries(value).filter(([k])=>!dropped.has(k.toLowerCase())&&k!=='identity_terms').map(([k,v])=>[k,scrub(v,terms,depth+1)]));
    if(typeof value!=='string')return value;
    for(const term of terms) if(term) value=value.replace(new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'),'[identity removed]');
    return value.replace(/[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/gi,'[identity removed]')
      .replace(/(?:https?:\/\/|www\.)[^\s<>\]\["']+/gi,'[identity removed]')
      .replace(/(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[012])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)/g,'[identity removed]')
      .replace(/(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)/g,'[identity removed]')
      .replace(/(?:电话|手机|微信|联系人|负责人|地址|门店地址|姓名|品牌名称|公司名称|phone|contact|address)\s*[:：]\s*[^\n，,；;。]+/gi,'[identity removed]');
  }
  function prepare(data,terms=[]){
    if(!data||Array.isArray(data)||data.schema_version!=='3.0')throw Error('需要完整 v3 研究记录，不能提交标签摘要。');
    if(data.authorization?.status!=='authorized'||data.authorization?.purpose!=='internal_research'||!data.authorization?.basis)throw Error('当前资料没有覆盖内部研究用途的授权，请保留在本地。');
    if(data.deidentification?.reviewed!==true||data.deidentification?.residual_risk!=='low')throw Error('请先处理身份线索与组合识别风险。');
    terms=[...terms,...(data.deidentification.identity_terms||[])].filter(x=>typeof x==='string'&&x).sort((a,b)=>b.length-a.length);
    const clean=Object.fromEntries(Object.entries(data).filter(([k])=>!dropped.has(k.toLowerCase())).map(([k,v])=>[k,protocol.has(k)?v:scrub(v,terms)]));
    if(new TextEncoder().encode(JSON.stringify(clean)).length>256*1024)throw Error('记录超过256KB，请只保留相关证据。');
    return clean;
  }
  async function submit(data,endpoint='/case-report'){
    const payload=prepare(data); let response;
    try {response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(20000),credentials:'omit',referrerPolicy:'no-referrer',redirect:'error'});}
    catch(_){throw Error('尚未取得回执：网络失败。请保存本地补交文件后重试；同一提交编号不会重复入库。');}
    const result=await response.json().catch(()=>({}));
    if(!response.ok||result.ok!==true||!['accepted','duplicate'].includes(result.status)||typeof result.receipt_id!=='string'||!result.receipt_id||result.case_id!==payload.case_id||result.submission_id!==payload.submission_id)throw Error('尚未接收：'+(result.error?.message||result.message||result.code||response.status));
    return result;
  }
  function id(prefix){return prefix+crypto.randomUUID().replaceAll('-','');}
  function download(value,name){const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}
  global.ZmxxResearch={prepare,submit,id,download,scrub};
})(globalThis);
