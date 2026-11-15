const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {join}=require('node:path');
const {runInNewContext}=require('node:vm');
const source=readFileSync(join(__dirname,'../theme.js'),'utf8');
function setup({saved=null,darkOS=false,brokenRead=false,brokenWrite=false,noMedia=false,forcedDark=false}={}){
 const classes=new Set(forcedDark?['force-dark']:[]),calls=[],events=[],attrs={};
 const button={textContent:'',setAttribute(k,v){attrs[k]=v;},addEventListener(k,fn){this[k]=fn;}};
 const html={style:{},classList:{contains:k=>classes.has(k),toggle(k,on){on?classes.add(k):classes.delete(k);}}};
 const window={localStorage:{getItem(k){calls.push(['get',k]);if(brokenRead)throw new Error('denied');return saved;},setItem(k,v){calls.push(['set',k,v]);if(brokenWrite)throw new Error('denied');}},dispatchEvent(event){events.push(event);}};
 if(!noMedia)window.matchMedia=()=>({matches:darkOS});
 runInNewContext(source,{window,document:{documentElement:html,readyState:'complete',getElementById:id=>id==='themeToggle'?button:null},CustomEvent:function(type,init){this.type=type;this.detail=init.detail;}});
 return {window,button,html,classes,calls,events,attrs};
}
test('saved valid theme wins; visible native button exposes destination and dark pressed state',()=>{
 const h=setup({saved:'dark',darkOS:false});assert.equal(h.window.getTheme(),'dark');assert.equal(h.button.textContent,'Use light');assert.equal(h.attrs['aria-label'],'Switch to light mode');assert.equal(h.attrs['aria-pressed'],'true');h.button.click();assert.equal(h.window.getTheme(),'light');assert.equal(h.button.textContent,'Use dark');assert.equal(h.attrs['aria-pressed'],'false');assert.deepEqual(h.calls.at(-1),['set','digin-theme','light']);
});
test('unavailable storage preserves functional tab-local theme without aborting startup',()=>{
 const h=setup({brokenRead:true,brokenWrite:true,darkOS:true});assert.equal(h.window.getTheme(),'dark');h.button.click();assert.equal(h.window.getTheme(),'light');assert.equal(h.html.style.colorScheme,'light');assert.equal(h.events.at(-1).detail,'light');
});
test('invalid stored/input theme and absent matchMedia have bounded light fallback',()=>{
 const h=setup({saved:'anything',noMedia:true});assert.equal(h.window.getTheme(),'light');const before=h.calls.length;assert.equal(h.window.setTheme('<script>'),false);assert.equal(h.calls.length,before);assert.equal(h.window.getTheme(),'light');
});
test('only the theme preference is persisted and forced-dark kitchen cannot be changed',()=>{
 const h=setup();h.window.setTheme('dark');h.window.setTheme('light');assert.ok(h.calls.every(call=>call[1]==='digin-theme'));const kitchen=setup({forcedDark:true});assert.equal(kitchen.calls.length,0);assert.equal(kitchen.window.setTheme,undefined);assert.ok(kitchen.classes.has('force-dark'));
});
test('both canonical server pages expose the theme button; Kitchen keeps forced dark and no theme runtime',()=>{
 for(const name of ['server-order','server-tables']){const page=readFileSync(join(__dirname,`../${name}.html`),'utf8');assert.match(page,/<script src="theme\.js"><\/script>/);assert.match(page,/id="themeToggle"[^>]*aria-label="Switch color theme"/);assert.match(page,/operator-pages\.js/);}
 const kitchen=readFileSync(join(__dirname,'../kitchen.html'),'utf8');assert.match(kitchen,/class="force-dark"/);assert.doesNotMatch(kitchen,/<script[^>]*theme\.js/);
});
