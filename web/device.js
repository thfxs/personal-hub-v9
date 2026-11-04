(function(){'use strict';
 var $=function(x){return document.getElementById(x)},N=window.PersonalHubFiles;
 function message(s){$('message').textContent=s;}
 try{$('swipe').checked=localStorage.getItem('personal_hub_landscape_swipe')!=='off';}
 catch(e){message('本机存储不可用，滑动偏好可能无法保存');}
 $('swipe').addEventListener('change',function(){try{localStorage.setItem('personal_hub_landscape_swipe',this.checked?'on':'off');message('横屏滑动偏好已保存在本机');}catch(e){message('偏好存储失败：'+e.message);}});
 if(!N||!N.isNative()){ $('immersive').disabled=true;$('awake').disabled=true;$('save').disabled=true;message(N&&N.isShell()?'当前 Android WebView 太旧，缺少安全消息通道；请先升级系统 WebView，原生设置/备份不可用。':'当前为网页/PWA 模式；原生显示设置需要 Android APK。横屏滑动偏好仍可使用。');return; }
 N.deviceStatus().then(function(s){$('immersive').checked=!!s.immersive;$('awake').checked=!!s.awake;message('已读取本机 Android 设置。');}).catch(function(e){message('读取设备设置失败：'+e.message);});
 $('save').addEventListener('click',function(){if($('awake').checked&&!window.confirm('长期亮屏会增加耗电、发热及 OLED 烧屏风险。确定保持亮屏吗？'))return;
  $('save').disabled=true;N.devicePreferences($('immersive').checked,$('awake').checked).then(function(){message('手机设备设置已保存。');}).catch(function(e){message('设置失败：'+e.message);}).finally(function(){$('save').disabled=false;});
 });
})();
