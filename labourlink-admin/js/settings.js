const API="http://localhost:5000/api/settings";

window.onload=()=>{

loadSettings();

};

async function loadSettings(){

try{

const res=await fetch(API);

const data=await res.json();

document.getElementById("companyName").value=data.companyName;

document.getElementById("supportEmail").value=data.supportEmail;

document.getElementById("phone").value=data.phone;

document.getElementById("address").value=data.address;

document.getElementById("commission").value=data.commission;

document.getElementById("minimumWithdrawal").value=data.minimumWithdrawal;

document.getElementById("currency").value=data.currency;

document.getElementById("facebook").value=data.facebook;

document.getElementById("instagram").value=data.instagram;

document.getElementById("linkedin").value=data.linkedin;

document.getElementById("logoPreview").src=data.logo;

}

catch(err){

alert("Unable to load settings");

}

}

document.getElementById("settingsForm").addEventListener("submit",saveSettings);

async function saveSettings(e){

e.preventDefault();

const data={

companyName:companyName.value,

supportEmail:supportEmail.value,

phone:phone.value,

address:address.value,

commission:Number(commission.value),

minimumWithdrawal:Number(minimumWithdrawal.value),

currency:currency.value,

facebook:facebook.value,

instagram:instagram.value,

linkedin:linkedin.value

};

try{

await fetch(API,{

method:"PUT",

headers:{

"Content-Type":"application/json"

},

body:JSON.stringify(data)

});

const file=document.getElementById("logoFile").files[0];

if(file){

const formData=new FormData();

formData.append("logo",file);

await fetch(API+"/logo",{

method:"POST",

body:formData

});

}

alert("Settings Updated Successfully");

loadSettings();

}

catch(err){

alert("Unable to save settings");

}

}

document.getElementById("logoFile").addEventListener("change",function(){

const file=this.files[0];

if(file){

document.getElementById("logoPreview").src=URL.createObjectURL(file);

}

});