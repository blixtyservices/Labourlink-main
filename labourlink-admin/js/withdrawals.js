const API="http://localhost:5000/api/withdrawals";

let withdrawals=[];

window.onload=()=>{

loadWithdrawals();

loadStats();

};

async function loadStats(){

const res=await fetch(API+"/stats");

const data=await res.json();

document.getElementById("totalRequest").innerHTML=data.total;

document.getElementById("pendingRequest").innerHTML=data.pending;

document.getElementById("approvedRequest").innerHTML=data.approved;

document.getElementById("totalPaid").innerHTML="₹"+data.totalPaid;

}

async function loadWithdrawals(){

const res=await fetch(API);

withdrawals=await res.json();

renderTable(withdrawals);

}

function renderTable(data){

const table=document.getElementById("withdrawTable");

table.innerHTML="";

data.forEach(item=>{

table.innerHTML+=`

<tr>

<td>${item.workerName}</td>

<td>₹${item.amount}</td>

<td>${item.bankName}</td>

<td>${item.accountNumber}</td>

<td>${item.ifsc}</td>

<td>

${
item.status==="Pending"
?'<span class="badge bg-warning text-dark">Pending</span>'
:item.status==="Approved"
?'<span class="badge bg-success">Approved</span>'
:'<span class="badge bg-danger">Rejected</span>'
}

</td>

<td>${new Date(item.createdAt).toLocaleDateString()}</td>

<td>

${
item.status==="Pending"

?

`

<button class="btn btn-success btn-sm"

onclick="approveWithdrawal('${item._id}')">

Approve

</button>

<button class="btn btn-danger btn-sm"

onclick="rejectWithdrawal('${item._id}')">

Reject

</button>

`

:

'<span class="text-muted">Completed</span>'

}

</td>

</tr>

`;

});

}

async function approveWithdrawal(id){

if(!confirm("Approve Withdrawal?")) return;

await fetch(API+"/"+id+"/approve",{

method:"PUT"

});

loadWithdrawals();

loadStats();

}

async function rejectWithdrawal(id){

if(!confirm("Reject Withdrawal?")) return;

await fetch(API+"/"+id+"/reject",{

method:"PUT"

});

loadWithdrawals();

loadStats();

}

function searchWithdrawal(){

const keyword=document.getElementById("searchInput").value.toLowerCase();

const result=withdrawals.filter(item=>

item.workerName.toLowerCase().includes(keyword)

);

renderTable(result);

}

function filterWithdrawal(){

const status=document.getElementById("statusFilter").value;

if(status===""){

renderTable(withdrawals);

return;

}

renderTable(

withdrawals.filter(item=>item.status===status)

);

}