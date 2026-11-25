'use strict';
const $ = id => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
let menu = [], modifiers = [], selected = null, activeCategory = 'Усі';
let cart = [];
try { const stored = JSON.parse(localStorage.getItem('sushiwave_cart') || '[]'); if (Array.isArray(stored)) cart = stored.filter(x => Number.isInteger(x.id) && Number.isInteger(x.quantity) && x.quantity > 0 && Array.isArray(x.modifiers)); } catch { cart = []; }
const money = n => `${n} ₴`;
const save = () => localStorage.setItem('sushiwave_cart', JSON.stringify(cart));
const show = name => { $(name).hidden = false; document.body.classList.add('locked'); };
const hide = name => { $(name).hidden = true; if (![...document.querySelectorAll('.overlay')].some(x => !x.hidden)) document.body.classList.remove('locked'); };
const product = id => menu.find(p => p.id === id);
const selectedModifiers = ids => modifiers.filter(m => ids.includes(m.id));
const unitPrice = line => { const p = product(line.id); return p ? p.price + selectedModifiers(line.modifiers).reduce((s,m) => s+m.price,0) : 0; };
function renderMenu(){
 const query = $('search').value.trim().toLocaleLowerCase('uk');
 let filtered = menu.filter(p => (activeCategory === 'Усі' || p.category === activeCategory) && (p.name+' '+p.description).toLocaleLowerCase('uk').includes(query));
 switch ($('sort').value){case 'cheap':filtered.sort((a,b)=>a.price-b.price);break;case 'expensive':filtered.sort((a,b)=>b.price-a.price);break;case 'name':filtered.sort((a,b)=>a.name.localeCompare(b.name,'uk'));break;}
 $('resultCount').textContent = `Знайдено страв: ${filtered.length}`;
 const grid = $('productGrid');grid.replaceChildren();
 if (!filtered.length){const p=document.createElement('p');p.textContent='Страв за вашим запитом не знайдено.';grid.append(p);return;}
 filtered.forEach(p=>{
  const card=document.createElement('article');card.className='product-card'+(!p.available?' out-of-stock':'');
  const art=document.createElement('div');art.className='product-art';
  const tag=document.createElement('span');tag.className='tag';tag.textContent=p.available?p.category:'Немає в наявності';
  const food=document.createElement('span');food.className='food';food.textContent=p.emoji;art.append(tag,food);
  const body=document.createElement('div');body.className='product-body';
  const title=document.createElement('h3');title.textContent=p.name;
  const desc=document.createElement('p');desc.className='product-desc';desc.textContent=p.description;
  const bottom=document.createElement('div');bottom.className='product-bottom';
  const price=document.createElement('strong');price.textContent=money(p.price);
  const btn=document.createElement('button');btn.className='btn btn-primary';btn.type='button';btn.textContent=p.available?'Обрати +':'Недоступно';btn.disabled=!p.available;btn.addEventListener('click',()=>openDetails(p));
  bottom.append(price,btn);body.append(title,desc,bottom);card.append(art,body);grid.append(card);
 });
}
function openDetails(p){selected=p;$('detailsEmoji').textContent=p.emoji;$('detailsCategory').textContent=p.category;$('detailsTitle').textContent=p.name;$('detailsDescription').textContent=p.description;$('detailsAllergens').textContent=`Інформація про алергени: ${p.allergens}`;
 $('modifierOptions').replaceChildren();modifiers.forEach(m=>{const label=document.createElement('label');const input=document.createElement('input');input.type='checkbox';input.value=m.id;input.addEventListener('change',updateDetailsPrice);const text=document.createElement('span');text.textContent=`${m.name} (+${m.price} ₴)`;label.append(input,text);$('modifierOptions').append(label);});updateDetailsPrice();show('detailsOverlay');$('closeDetails').focus();}
function updateDetailsPrice(){if(!selected)return;const ids=[...$('modifierOptions').querySelectorAll(':checked')].map(x=>Number(x.value));$('detailsPrice').textContent=money(selected.price+selectedModifiers(ids).reduce((sum,m)=>sum+m.price,0));}
function addConfigured(){if(!selected)return;const ids=[...$('modifierOptions').querySelectorAll(':checked')].map(x=>Number(x.value));const existing=cart.find(c=>c.id===selected.id&&JSON.stringify(c.modifiers)===JSON.stringify(ids));if(existing){if(existing.quantity>=20){alert('Максимум 20 одиниць одного виду.');return;}existing.quantity++;}else cart.push({id:selected.id,quantity:1,modifiers:ids});save();renderCart();hide('detailsOverlay');show('cartOverlay');$('closeCart').focus();}
function changeQuantity(i,change){cart[i].quantity+=change;if(cart[i].quantity<=0)cart.splice(i,1);if(cart[i]&&cart[i].quantity>20)cart[i].quantity=20;save();renderCart();}
function renderCart(){cart=cart.filter(c=>product(c.id));$('cartItems').replaceChildren();let total=0,count=0;
 cart.forEach((line,i)=>{const p=product(line.id),price=unitPrice(line)*line.quantity;total+=price;count+=line.quantity;
 const row=document.createElement('div');row.className='cart-row';const left=document.createElement('div');const name=document.createElement('strong');name.textContent=p.name;const ex=document.createElement('small');ex.textContent=selectedModifiers(line.modifiers).map(m=>m.name).join(', ')||'Без додатків';const amount=document.createElement('small');amount.textContent=money(price);left.append(name,ex,amount);
 const qty=document.createElement('div');qty.className='qty';const minus=document.createElement('button');minus.textContent='−';minus.setAttribute('aria-label',`Зменшити ${p.name}`);minus.addEventListener('click',()=>changeQuantity(i,-1));const n=document.createElement('span');n.textContent=line.quantity;const plus=document.createElement('button');plus.textContent='+';plus.setAttribute('aria-label',`Збільшити ${p.name}`);plus.addEventListener('click',()=>changeQuantity(i,1));qty.append(minus,n,plus);row.append(left,qty);$('cartItems').append(row);});
 if(!cart.length){const msg=document.createElement('p');msg.textContent='Тут поки порожньо. Додайте щось смачненьке!';$('cartItems').append(msg);}
 $('cartTotal').textContent=total;$('cartCount').textContent=count;$('checkoutTotal').textContent=money(total);$('goCheckout').disabled=!cart.length;
}
function setPickupDefault(){const d=new Date(Date.now()+90*60000);d.setMinutes(d.getMinutes()<30?30:0);if(d.getMinutes()===0)d.setHours(d.getHours()+1);if(d.getHours()<11)d.setHours(11,0);if(d.getHours()>21||(d.getHours()===21&&d.getMinutes()>0)){d.setDate(d.getDate()+1);d.setHours(11,0);}const local=new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);$('pickup').value=local;}
async function checkout(e){e.preventDefault();$('checkoutError').textContent='';const form=e.currentTarget;const button=$('submitOrder');button.disabled=true;button.textContent='Зберігаємо...';
 const payload={name:form.elements.name.value,phone:form.elements.phone.value,pickup_at:form.elements.pickup.value,comment:form.elements.comment.value,items:cart.map(c=>({id:c.id,quantity:c.quantity,modifiers:c.modifiers}))};
 try{const res=await fetch('/api/orders',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(payload)});const data=await res.json();if(!res.ok)throw new Error(data.error||'Не вдалося оформити замовлення');cart=[];save();window.location.assign(data.tracking_url);}catch(err){$('checkoutError').textContent=err.message;button.disabled=false;button.textContent='Підтвердити замовлення';}}
async function init(){try{const res=await fetch('/api/menu');if(!res.ok)throw new Error('Сервер недоступний');const data=await res.json();menu=data.products;modifiers=data.modifiers;renderMenu();renderCart();}catch(err){$('resultCount').textContent=err.message;}}
$('categoryButtons').addEventListener('click',e=>{const b=e.target.closest('button[data-category]');if(!b)return;activeCategory=b.dataset.category;document.querySelectorAll('.categories button').forEach(x=>x.classList.toggle('active',x===b));renderMenu();});
$('search').addEventListener('input',renderMenu);$('sort').addEventListener('change',renderMenu);
$('openCart').addEventListener('click',()=>{show('cartOverlay');$('closeCart').focus();});
$('closeCart').addEventListener('click',()=>hide('cartOverlay'));
$('closeDetails').addEventListener('click',()=>hide('detailsOverlay'));
$('closeCheckout').addEventListener('click',()=>hide('checkoutOverlay'));
$('addConfigured').addEventListener('click',addConfigured);
$('goCheckout').addEventListener('click',()=>{hide('cartOverlay');setPickupDefault();show('checkoutOverlay');});
$('checkoutForm').addEventListener('submit',checkout);
document.querySelectorAll('.overlay').forEach(o=>o.addEventListener('click',e=>{if(e.target===o)hide(o.id);}));
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.overlay').forEach(o=>{if(!o.hidden)hide(o.id);});});
init();
