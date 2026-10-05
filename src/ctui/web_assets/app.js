/* One shared app session; draft input, history, selection and scrolling stay local. */
'use strict';
const workspace = document.querySelector('#workspace');
const status = document.querySelector('#connection');
const login = document.querySelector('#login');
const suggestions = document.querySelector('#suggestions');
let socket, retry, stopped = false, sequence = 0, latestCommand = 0;
let completeSequence = 0, completeTimer, completionItems = [], completionIndex = 0;
let commandInput, shortcuts = [], draft = '', draftCursor = 0;
const elements = new Map(), history = [];
let historyIndex = 0;
const dialogs = [];

function send(message) {
  if (socket?.readyState === WebSocket.OPEN) { socket.send(JSON.stringify(message)); return true; }
  return false;
}
function notice(text) { status.textContent = text; status.classList.remove('connected'); }
function styleText(element, style) {
  // Only interpret known prompt-toolkit tokens; never accept arbitrary CSS/HTML.
  const colors = {ansired:'#c44', ansigreen:'#4c4', ansiyellow:'#cc4', ansiblue:'#44c', ansimagenta:'#c4c', ansicyan:'#4cc', ansiwhite:'#ddd', ansiblack:'#111', ansibrightcyan:'#4ff', ansibrightyellow:'#ff4'};
  for (const token of (style || '').split(/\s+/)) {
    if (token === 'bold') element.style.fontWeight = 'bold';
    else if (token === 'italic') element.style.fontStyle = 'italic';
    else if (token === 'underline') element.style.textDecoration = 'underline';
    else if (colors[token]) element.style.color = colors[token];
    else if (/^#[0-9a-f]{6}$/i.test(token)) element.style.color = token;
    else if (/^bg:#[0-9a-f]{6}$/i.test(token)) element.style.backgroundColor = token.slice(3);
    else if (token.startsWith('class:')) {
      for (const name of token.slice(6).split(',')) if (/^[\w-]+$/.test(name)) element.classList.add(name);
    }
  }
}
function rememberDraft() {
  if (commandInput) { draft = commandInput.value; draftCursor = commandInput.selectionStart; }
}
function requestCompletion() {
  clearTimeout(completeTimer);
  const id = ++completeSequence;
  completeTimer = setTimeout(() => send({type:'complete', id, text:commandInput.value, cursor:commandInput.selectionStart}), 90);
}
function applyCompletion(item) {
  if (!item?.text || !commandInput) return;
  const cursor = commandInput.selectionStart;
  commandInput.setRangeText(item.text, Math.max(0, cursor + item.start), cursor, 'end');
  rememberDraft(); hideCompletions(); commandInput.focus(); requestCompletion();
}
function hideCompletions() { suggestions.hidden = true; completionItems = []; }
function showCompletions(items) {
  completionItems = items; completionIndex = 0; suggestions.replaceChildren();
  for (const [index,item] of items.entries()) {
    const element = document.createElement(item.text ? 'button' : 'div');
    element.textContent = `${item.display || item.text}  ${item.help || ''}`;
    element.className = item.text ? (index === 0 ? 'selected' : '') : 'hint';
    element.addEventListener('mousedown', event => event.preventDefault());
    if (item.text) element.addEventListener('click', () => applyCompletion(item));
    suggestions.append(element);
  }
  if (commandInput) {
    const rect = commandInput.getBoundingClientRect();
    suggestions.style.top = `${rect.bottom}px`; suggestions.style.left = `${rect.left}px`;
  }
  suggestions.hidden = !items.length;
}
function submitCommand() {
  const text = commandInput.value;
  if (!text.trim()) return;
  const id = ++sequence;
  if (!send({type:'command', id, text})) return;
  latestCommand = id; history.push(text); historyIndex = history.length;
  commandInput.value = ''; rememberDraft(); ++completeSequence; hideCompletions();
}
function render(node, parentAxis = 'height') {
  let element = elements.get(node.id);
  if (!element || element.dataset.kind !== node.kind) {
    const tag = {text:'pre', label:'div', frame:'fieldset', button:'button', editor:'textarea', separator:'div'}[node.kind] || 'div';
    element = document.createElement(tag); element.dataset.kind = node.kind; elements.set(node.id, element);
    if (node.kind === 'input') {
      const prompt = document.createElement('span'); const input = document.createElement('input');
      input.type = 'text'; input.setAttribute('aria-label','Command'); input.autocomplete = 'off'; input.spellcheck = false;
      input.value = draft;
      input.addEventListener('input', () => { rememberDraft(); requestCompletion(); });
      input.addEventListener('keydown', inputKey); element.append(prompt,input);
    } else if (node.kind === 'button') element.addEventListener('click', () => send({type:'button',id:node.id}));
    else if (node.kind === 'editor') element.addEventListener('input', () => send({type:'edit', id:node.id, text:element.value}));
    else if (node.kind === 'frame') element.append(document.createElement('legend'));
    else if (node.kind === 'progress') { const bar=document.createElement('progress'); bar.max=100; element.append(bar,document.createElement('span')); }
  }
  element.className = `node ${node.kind}`; element.removeAttribute('style'); styleText(element,node.style);
  for (const axis of ['width','height']) {
    const size=node[axis]; if (!size || node.kind==='separator') continue;
    const unit=axis==='width'?'ch':'lh';
    if (size.max < 1000000000 && size.min === size.max) {
      element.style[axis]=`${size.min}${unit}`;
      if (axis===parentAxis) element.style.flex=`0 0 ${size.min}${unit}`;
    } else {
      if (size.min) element.style[axis==='width'?'minWidth':'minHeight']=`${size.min}${unit}`;
      if (size.max < 1000000000) element.style[axis==='width'?'maxWidth':'maxHeight']=`${size.max}${unit}`;
      if (axis===parentAxis && node.kind!=='label') element.style.flex=`${size.weight || 1} 1 ${size.preferred ? size.preferred+unit : '0'}`;
    }
  }
  if (node.kind === 'input') { element.firstChild.textContent=node.prompt; commandInput=element.lastChild; }
  else if (node.kind === 'text') {
    element.classList.toggle('wrap',node.wrap);
    if (element.textContent !== node.text) {
      const bottom=element.scrollHeight-element.scrollTop-element.clientHeight < 30;
      element.textContent=node.text;
      if (bottom) requestAnimationFrame(() => {element.scrollTop=element.scrollHeight;});
    }
  } else if (node.kind === 'label') {
    const content=JSON.stringify(node.fragments);
    if (element.dataset.content!==content) {
      element.dataset.content=content; element.replaceChildren();
      for (const [style,text] of node.fragments) {const span=document.createElement('span');span.textContent=text;styleText(span,style);element.append(span);}
    }
  } else if (node.kind === 'editor' && document.activeElement!==element) element.value=node.text;
  else if (node.kind === 'button') element.textContent=node.text;
  else if (node.kind === 'progress') {element.firstChild.value=node.value;element.lastChild.textContent=`${node.value}%`;}
  else if (node.kind === 'frame') element.firstChild.textContent=node.title;
  if (node.children) {
    const wanted=node.children.map(child => render(child,node.kind==='horizontal'?'width':'height'));
    if (node.kind==='frame') wanted.unshift(element.firstChild);
    // Retain nodes in place to preserve native focus, selection, and scroll state.
    wanted.forEach((child,index) => {if (element.children[index]!==child) element.insertBefore(child,element.children[index] || null);});
    for (const child of [...element.children]) if (!wanted.includes(child)) child.remove();
  }
  return element;
}
function inputKey(event) {
  if (event.key==='Enter') {event.preventDefault();submitCommand();}
  else if (event.key==='Tab') {event.preventDefault();if (!suggestions.hidden) applyCompletion(completionItems[completionIndex]);else requestCompletion();}
  else if (event.key==='Escape') hideCompletions();
  else if ((event.key==='ArrowUp'||event.key==='ArrowDown')&&!event.ctrlKey) {
    event.preventDefault(); const direction=event.key==='ArrowUp'?-1:1;
    if (!suggestions.hidden && completionItems.some(item=>item.text)) {
      completionIndex=(completionIndex+direction+completionItems.length)%completionItems.length;
      [...suggestions.children].forEach((child,index)=>child.classList.toggle('selected',index===completionIndex));
    } else {historyIndex=Math.max(0,Math.min(history.length,historyIndex+direction));commandInput.value=history[historyIndex]||'';rememberDraft();}
  } else if (event.ctrlKey && ['c','l','a','e','u','k','d'].includes(event.key.toLowerCase())) {
    event.preventDefault();const start=commandInput.selectionStart,end=commandInput.selectionEnd;
    switch(event.key.toLowerCase()) {
      case 'c':commandInput.value='';hideCompletions();break;
      case 'l':send({type:'clear'});break;
      case 'a':commandInput.setSelectionRange(0,0);break;
      case 'e':commandInput.setSelectionRange(commandInput.value.length,commandInput.value.length);break;
      case 'u':commandInput.setRangeText('',0,start,'start');break;
      case 'k':commandInput.setRangeText('',end,commandInput.value.length,'end');break;
      case 'd':if (!commandInput.value) send({type:'exit'});else commandInput.setRangeText('',start,Math.min(commandInput.value.length,start+1),'start');break;
    }
    rememberDraft();
  } else if (['PageUp','PageDown','Home','End'].includes(event.key) || (event.ctrlKey&&['ArrowUp','ArrowDown'].includes(event.key))) {
    event.preventDefault();const output=workspace.querySelector('.output_field');if (!output) return;
    const amount=event.key==='Home'?-output.scrollHeight:event.key==='End'?output.scrollHeight:(event.key==='PageUp'?-1:event.key==='PageDown'?1:event.key==='ArrowUp'?-0.05:0.05)*output.clientHeight;
    output.scrollTop+=amount;
  }
}
function openDialog(message) {
  dialogs.push(message);if (dialogs.length===1) displayDialog();
}
function displayDialog() {
  const message=dialogs[0];if (!message) return;
  const dialog=document.createElement('dialog'),title=document.createElement('h2'),text=document.createElement('pre'),actions=document.createElement('div');
  title.textContent=message.title;text.textContent=message.text;actions.className='actions';dialog.append(title,text);
  let input;
  if (message.input) {input=document.createElement('input');input.type=message.input.password?'password':'text';input.setAttribute('aria-label',message.title);dialog.append(input);}
  function answer(button) {send({type:'answer',id:message.id,button,text:input?.value||''});dialog.close();dialog.remove();dialogs.shift();displayDialog();if(!dialogs.length)commandInput?.focus();}
  message.buttons.forEach((label,index)=>{const button=document.createElement('button');button.textContent=label;button.addEventListener('click',()=>answer(index));actions.append(button);});
  dialog.addEventListener('keydown',event=>{
    if(event.target===input){if(event.key==='Enter'){event.preventDefault();actions.firstChild.focus();}return;}
    const scroll={ArrowUp:-1,ArrowDown:1,PageUp:-text.clientHeight/21,PageDown:text.clientHeight/21};
    if(event.key in scroll){event.preventDefault();text.scrollTop+=scroll[event.key]*21;}
    else if(event.key==='ArrowLeft'||event.key==='ArrowRight'){
      event.preventDefault();const buttons=[...actions.children],index=buttons.indexOf(document.activeElement);
      buttons[(index+(event.key==='ArrowLeft'?-1:1)+buttons.length)%buttons.length].focus();
    }
  });
  dialog.append(actions);document.querySelector('#dialogs').append(dialog);dialog.addEventListener('cancel',event=>{event.preventDefault();answer(message.buttons.length-1);});dialog.showModal();(input||actions.firstChild).focus();
}
function connect() {
  clearTimeout(retry);socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);
  socket.onopen=()=>{login.hidden=true;workspace.hidden=false;status.classList.add('connected');};
  socket.onmessage=event=>{
    const message=JSON.parse(event.data);
    if(message.type==='state') {
      rememberDraft();document.title=message.name;shortcuts=message.shortcuts;
      const focused=document.activeElement;const root=render(message.layout);
      if(workspace.firstChild!==root)workspace.replaceChildren(root);
      if(!focused||focused===document.body)commandInput?.focus();
      // Prune detached widgets when dynamic layouts change.
      for(const [id,element] of elements)if(!workspace.contains(element))elements.delete(id);
    } else if(message.type==='completion'&&message.id===completeSequence) showCompletions(message.items);
    else if(message.type==='dialog')openDialog(message);
    else if(message.type==='error'||message.type==='rejected') {
      if(message.id===latestCommand&&commandInput&&!commandInput.value){commandInput.value=message.text;const pos=message.position??message.text.length;commandInput.setSelectionRange(pos,pos);rememberDraft();}
      if(message.message)openDialog({title:'Error',text:message.message,buttons:['OK']});
    } else if(message.type==='session-ended') {
      stopped=true;clearTimeout(retry);
      notice('Session stopped. You can close this tab.');
      if(message.close_tab)window.close();
    } else if(message.type==='notice')notice(message.message);
  };
  socket.onclose=event=>{
    for(const dialog of document.querySelectorAll('dialog'))dialog.remove();dialogs.length=0;hideCompletions();
    if(event.code===1001||stopped){stopped=true;notice('Session stopped. You can close this tab.');}
    else {notice('Disconnected. Reconnecting…');if(!stopped)retry=setTimeout(connect,1500);}
  };
}
document.addEventListener('keydown',event=>{
  if(document.querySelector('dialog'))return;
  if(event.ctrlKey&&event.key.toLowerCase()==='q'){event.preventDefault();send({type:'exit'});return;}
  const key=event.key.length===1?event.key.toLowerCase():event.key.toLowerCase().replace('arrow','');
  const name=(event.ctrlKey?'c-':'')+(event.altKey?'escape,':'')+key;
  // Single keys and sequences are mapped to prompt-toolkit names.
  keySequence.push(name);if(keySequence.length>8)keySequence.shift();clearTimeout(sequenceTimer);sequenceTimer=setTimeout(()=>keySequence.length=0,1000);
  for(const keys of shortcuts)if(keys.join('|')===keySequence.slice(-keys.length).join('|')){event.preventDefault();event.stopPropagation();send({type:'shortcut',keys});keySequence.length=0;break;}
},true);
const keySequence=[];let sequenceTimer;
async function authenticate(token) {
  try {
    const response=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
    if(!response.ok)throw new Error('Invalid session token');
    document.querySelector('#token').value='';stopped=false;connect();
  } catch(error){notice(error.message);login.hidden=false;}
}
document.querySelector('#login-form').addEventListener('submit',event=>{event.preventDefault();authenticate(document.querySelector('#token').value);});
const token=new URLSearchParams(location.hash.slice(1)).get('token');
if(token){window.history.replaceState(null,'',location.pathname);authenticate(token);}
else connect();
