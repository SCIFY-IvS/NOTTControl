const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const live=path.resolve(__dirname,'../../../../HMI/nott_cryo_hmi/nott_cryo_hmi');
const stage=path.join(__dirname,'files'),manifest=[];
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
function read(f){return fs.readFileSync(path.join(live,f),'utf8');}
function save(f,s){const target=path.join(live,f),file=path.join(stage,f);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,s);manifest.push({target,stage:file,hash:fs.existsSync(target)?hash(fs.readFileSync(target)):null});}
function opening(html,id,fn){const re=new RegExp('<div\\b[^>]*\\bid="'+id+'"[^>]*>');if(!re.test(html))throw Error('Missing control '+id);return html.replace(re,fn);}
function attr(tag,k,v){const re=new RegExp(' '+k+'="[^"]*"');const a=' '+k+'="'+v+'"';return re.test(tag)?tag.replace(re,a):tag.slice(0,-1)+a+'>';}
const tb='ADS.NOTT_CRYO_PLC.MAIN.nott_cryo_ctrl.thermal_box_ctrl.stat';
const dp='ADS.NOTT_CRYO_PLC.MAIN.nott_detector_power.stat';
function indicator(id,x,y,label,state,valid){return '<div id="'+id+'" data-tchmi-type="TcHmi.Controls.CryoFramework.LedBox" data-tchmi-left="'+x+'" data-tchmi-top="'+y+'" data-tchmi-width="20" data-tchmi-height="20" data-tchmi-left-unit="px" data-tchmi-top-unit="px" data-tchmi-width-unit="px" data-tchmi-height-unit="px" data-tchmi-zindex="150" data-tchmi-ledbox-blink="false" data-tchmi-ledbox-state="%s%'+state+'%/s%" data-tchmi-datalabel-data-valid="'+valid+'"></div>\n'+
'<div id="'+id+'_Label" data-tchmi-type="TcHmi.Controls.Beckhoff.TcHmiTextblock" data-tchmi-left="'+(x+28)+'" data-tchmi-top="'+y+'" data-tchmi-width="110" data-tchmi-height="20" data-tchmi-text="'+label+'" data-tchmi-text-font-size="14" data-tchmi-text-vertical-alignment="Center" data-tchmi-zindex="150"></div>\n';}
let thermal=read('Pages/ThermalBox.content');
thermal=opening(thermal,'ThermalBox',tag=>tag+'\n'+indicator('ThermalBox_EnabledLed',20,8,'Enabled',tb+'::bActive','%f%typeof %s%'+tb+'::bActive%/s% === \'boolean\'%/f%'));
save('Pages/ThermalBox.content',thermal);
let detector=read('Pages/DetectorPower.content');
detector=opening(detector,'DetectorPower_Title',tag=>attr(tag,'data-tchmi-width','220'));
detector=opening(detector,'DetectorPower',tag=>tag+'\n'+indicator('DetectorPower_EnabledLed',265,15,'Power enabled',dp+'::bPowerOn','%s%'+dp+'::bFuseOperational%/s%'));
save('Pages/DetectorPower.content',detector);
const trigger=['Attached','Detached'].map((event,i)=>({event:'%ctx%owner::Id|EventRegistrationMode=Resolve%/ctx%.on'+event,actions:[{objectType:'Function',active:true,fn:'TcHmi.Functions.NOTT.NOTTHeaderStatus',fnParams:[{objectType:'Symbol',valueType:'tchmi:general#/definitions/String',symbolExpression:'%ctx%owner::Id%/ctx%'},{objectType:'StaticValue',valueType:'tchmi:general#/definitions/String',value:i?'Detach':'Attach'}],asyncWait:true}]}));
let header=read('Pages/Header.content');
header=opening(header,'Header',tag=>tag+'\n<script type="application/json" data-tchmi-target-attribute="data-tchmi-trigger">'+JSON.stringify(trigger,null,2)+'</script>\n');
save('Pages/Header.content',header);
const js='JavaScript/NOTTHeaderStatus.js',css='Styles/NOTTStatus.css',fn='JavaScript/NOTTHeaderStatus.function.json';
save(js,fs.readFileSync(path.join(stage,js),'utf8'));save(css,fs.readFileSync(path.join(stage,css),'utf8'));
save(fn,JSON.stringify({function:{name:'NOTTHeaderStatus',namespace:'TcHmi.Functions.NOTT',displayName:'NOTT Header Status',description:'Read-only header status subscriptions.',waitMode:'Synchronous',category:'NOTT',returnValue:null,visible:true,injectContextObject:false,arguments:['ownerId','action'].map(name=>({name,displayName:name,type:'tchmi:general#/definitions/String',description:name,defaultValue:''}))},$schema:'../../Packages/Beckhoff.TwinCAT.HMI.Framework.14.6.3/runtimes/native1.12-tchmi/Schema/FunctionDescription.Schema.json',apiVersion:1,dependencyFiles:[]},null,2)+'\n');
const cfg=JSON.parse(read('Properties/tchmiconfig.json'));
for(const [name,type]of [[js,'JavaScript'],[css,'Stylesheet']])if(!cfg.dependencyFiles.some(d=>d.name===name))cfg.dependencyFiles.push({name,type,description:'NOTT status indicators'});
if(!cfg.userFunctions.some(f=>f.url===js))cfg.userFunctions.push({url:js});
save('Properties/tchmiconfig.json',JSON.stringify(cfg,null,2)+'\n');
let project=read('nott_cryo_hmi.hmiproj');
const entries=[js,css,fn].map(f=>f.replaceAll('/','\\')).filter(f=>!project.includes('Include="'+f+'"')).map(f=>'    <Content Include="'+f+'" />').join('\r\n');
if(entries)project=project.replace('</Project>','  <ItemGroup>\r\n'+entries+'\r\n  </ItemGroup>\r\n</Project>');
save('nott_cryo_hmi.hmiproj',project);
fs.writeFileSync(path.join(__dirname,'manifest.json'),JSON.stringify(manifest,null,2));
console.log('Prepared '+manifest.length+' HMI-only source files.');
