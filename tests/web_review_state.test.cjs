// Native Node tests with a fake DOM/network. No browser, server or model starts.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function deferred() {
  let resolve, reject;
  const promise = new Promise((a,b) => {resolve=a; reject=b;});
  return {promise,resolve,reject};
}
function setup() {
  const nodes = new Map(), pending = deferred(), calls = [];
  function element(id) {
    if (!nodes.has(id)) nodes.set(id, {
      value:'',textContent:'',disabled:false,hidden:false,
      addEventListener(){},reset(){},classList:{add(){},remove(){}},
      getContext:()=>({clearRect(){}}),naturalWidth:1,naturalHeight:1,
    });
    return nodes.get(id);
  }
  const sandbox = {
    document:{getElementById:element,querySelectorAll:()=>[]},
    sessionStorage:{getItem:()=>null,removeItem(){},setItem(){}},
    setTimeout(){},console,URL:{revokeObjectURL(){},createObjectURL:()=> 'blob:fixture'},
    crypto:{randomUUID:()=> 'fixture-token'},
    fetch:async (url,options) => {
      if(url.endsWith('/review')) {calls.push({url,options}); return pending.promise;}
      return {ok:true,json:async()=> url==='/api/session' ? {max_bytes:1000,retention_hours:24} : {ready:true}};
    },
  };
  vm.createContext(sandbox);
  const source=fs.readFileSync(path.join(__dirname,'../src/docucheck/web/static/app.js'),'utf8');
  vm.runInContext(source + `\nglobalThis.hooks={save,choose,buttons,setJob(job){latest=job;busy=false;dirty=false;},getJob(){return latest;}};`,sandbox);
  const values={seller_name:'SHOP',seller_address:'Road',transaction_datetime:null,total_amount:100};
  const job={id:'first',result:values,revision:0,state:'partial',review:null,
    fields:Object.fromEntries(Object.keys(values).map(k=>[k,{status:'ok',issues:[]}]))};
  sandbox.hooks.setJob(job);
  element('seller_name').value='SHOP';element('seller_address').value='Road';
  element('total_amount').value='100';
  return {hooks:sandbox.hooks,nodes,element,pending,calls,job};
}

test('save locks fields, prevents duplicate submit, unlocks on success',async()=>{
  const s=setup();
  const saving=s.hooks.save(false);
  assert.equal(s.element('fields').disabled,true);
  assert.equal(s.element('save').disabled,true);
  await s.hooks.save(false);
  assert.equal(s.calls.length,1);
  const values=JSON.parse(s.calls[0].options.body).values;
  s.pending.resolve({ok:true,json:async()=>({review:{values,confirmed:false},revision:1})});
  await saving;
  assert.equal(s.element('fields').disabled,false);
  assert.equal(s.hooks.getJob().revision,1);
});

test('save failure unlocks form and preserves typed values',async()=>{
  const s=setup();
  s.element('seller_name').value='Edited merchant';
  const saving=s.hooks.save(false);
  s.pending.reject(new Error('network failed'));
  await saving;
  assert.equal(s.element('seller_name').value,'Edited merchant');
  assert.equal(s.element('fields').disabled,false);
  assert.match(s.element('error').textContent,/network failed/);
});

test('late save failure from previous image does not affect new image',async()=>{
  const s=setup();
  const saving=s.hooks.save(false);
  await s.hooks.choose({size:10,name:'second.png'});
  s.pending.reject(new Error('old request failed'));
  await saving;
  assert.equal(s.hooks.getJob(),null);
  assert.equal(s.element('error').textContent,'');
});

test('late save success cannot replace the new image result',async()=>{
  const s=setup();
  const saving=s.hooks.save(false);
  await s.hooks.choose({size:10,name:'second.png'});
  const newer={...s.job,id:'second',revision:5};
  s.hooks.setJob(newer);
  s.pending.resolve({ok:true,json:async()=>({review:{values:s.job.result,confirmed:true},revision:1})});
  await saving;
  assert.equal(s.hooks.getJob().id,'second');
  assert.equal(s.hooks.getJob().revision,5);
});
