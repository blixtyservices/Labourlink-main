const API="http://localhost:5000/api/payments";

let payments=[];

window.onload=()=>{

loadPayments();

loadStats();

};

async function loadStats(){

try{

const res=await fetch(API+"/stats");

const data=await res.json();

document.getElementById("totalRevenue").innerHTML="₹"+data.totalRevenue;

document.getElementById("todayRevenue").innerHTML="₹"+data.todayRevenue;

document.getElementById("pendingCount").innerHTML=data.pending;

document.getElementById("failedCount").innerHTML=data.failed;

}

catch(err){

console.log(err);

}

}

async function loadPayments(){

try{

const res=await fetch(API);

payments=await res.json();

renderTable(payments);

}

catch(err){

alert("Unable to load payments");

}

}

function renderTable(list){

const table=document.getElementById("paymentTable");

table.innerHTML="";

list.forEach(payment=>{

table.innerHTML+=`

<tr>

<td>${payment.paymentId}</td>

<td>${payment.userName}</td>

<td>${payment.workerName}</td>

<td>${payment.service}</td>

<td>₹${payment.amount}</td>

<td>${payment.method}</td>

<td>

${payment.status=="Success"

?'<span class="badge bg-success">Success</span>'

:payment.status=="Pending"

?'<span class="badge bg-warning text-dark">Pending</span>'

:'<span class="badge bg-danger">Failed</span>'}

</td>

<td>${new Date(payment.createdAt).toLocaleDateString()}</td>

<td>

<button
class="btn btn-info btn-sm"
onclick="viewPayment('${payment._id}')">

<i class="fa fa-eye"></i>

</button>

<button
class="btn btn-danger btn-sm"
onclick="deletePayment('${payment._id}')">

<i class="fa fa-trash"></i>

</button>

</td>

</tr>

`;

});

}

function searchPayment(){

const keyword=document.getElementById("searchInput").value.toLowerCase();

const filtered=payments.filter(p=>

p.paymentId.toLowerCase().includes(keyword)||

p.userName.toLowerCase().includes(keyword)||

p.workerName.toLowerCase().includes(keyword)||

p.service.toLowerCase().includes(keyword)

);

renderTable(filtered);

}

function filterStatus(){

const status=document.getElementById("statusFilter").value;

if(status==""){

renderTable(payments);

return;

}

const filtered=payments.filter(p=>p.status===status);

renderTable(filtered);

}

async function viewPayment(id){

const res=await fetch(API+"/"+id);

const payment=await res.json();

alert(

"Payment ID : "+payment.paymentId+

"\n\nUser : "+payment.userName+

"\nWorker : "+payment.workerName+

"\nService : "+payment.service+

"\nAmount : ₹"+payment.amount+

"\nMethod : "+payment.method+

"\nStatus : "+payment.status+

"\nDate : "+new Date(payment.createdAt).toLocaleString()

);

}

async function deletePayment(id){

if(!confirm("Delete Payment?")) return;

await fetch(API+"/"+id,{

method:"DELETE"

});

loadPayments();

loadStats();

}