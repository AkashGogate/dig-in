/* Ephemeral PCM producer and immutable capture-context guards. */
"use strict";
window.DigInVoiceAudio={
 pcm16(input,rate){
  if(!Number.isFinite(rate)||rate<16000)throw new Error("Unsupported audio rate");
  const ratio=rate/16000,out=new Int16Array(Math.floor(input.length/ratio));
  for(let n=0;n<out.length;n++){const first=Math.floor(n*ratio),last=Math.min(input.length,Math.floor((n+1)*ratio));let sum=0;for(let k=first;k<last;k++)sum+=input[k];const value=Math.max(-1,Math.min(1,sum/Math.max(1,last-first)));out[n]=Math.round(value*(value<0?32768:32767));}return out.buffer;
 },
 pin(target,c){return {target,session:c.session,actorId:c.actorId,view:c.view,orderId:target==="order"?c.order?.id:null,revision:target==="order"?c.order?.revision:null,menuRevision:target==="order"?c.order?.menu_revision:c.menuRevision};},
 matches(p,c){if(p.session!==c.session||p.actorId!==c.actorId||p.view!==c.view)return false;if(p.target==="kitchen")return c.view==="kitchen"&&p.menuRevision===c.menuRevision&&["cook","lead"].includes(c.role);return c.view==="server"&&c.order?.status==="draft"&&p.orderId===c.order?.id&&p.revision===c.order?.revision&&p.menuRevision===c.order?.menu_revision;}
};
