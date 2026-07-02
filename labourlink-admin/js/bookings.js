const API="http://localhost:5000/api/bookings";

let bookings=[];

window.onload=()=>{

loadBookings();

loadStats();

};

async function loadStats(){

try{

const res=await fetch(API+"/stats");

const stats=await res.json();

document.getElementById("totalBooking").innerHTML=stats.total;

document.getElementById("pendingBooking").innerHTML=stats.pending;

document.getElementById("acceptedBooking").innerHTML=stats.accepted;

document.getElementById("ongoingBooking").innerHTML=stats.ongoing;

document.getElementById("completedBooking").innerHTML=stats.completed;

document.getElementById("cancelBooking").innerHTML=stats.cancelled;

}

catch(err){

console.log(err);

}

}

async function loadBookings(){

try{

const res=await fetch(API);

bookings=await res.json();

renderTable(bookings);

}

catch(err){

alert("Unable to load bookings");

}

}

function renderTable(data){

const table=document.getElementById("bookingTable");

table.innerHTML="";

data.forEach(booking=>{

table.innerHTML+=`

<tr>

<td>${booking.bookingId}</td>

<td>${booking.customerName}</td>

<td>${booking.workerName || "Not Assigned"}</td>

<td>${booking.service}</td>

<td>₹${booking.amount}</td>

<td>

<select

class="form-select form-select-sm"

onchange="updateStatus('${booking._id}',this.value)">

<option ${booking.status=="Pending"?"selected":""}>Pending</option>

<option ${booking.status=="Accepted"?"selected":""}>Accepted</option>

<option ${booking.status=="Ongoing"?"selected":""}>Ongoing</option>

<option ${booking.status=="Completed"?"selected":""}>Completed</option>

<option ${booking.status=="Cancelled"?"selected":""}>Cancelled</option>

</select>

</td>

<td>

${new Date(booking.createdAt).toLocaleDateString()}

</td>

<td>

<button

class="btn btn-info btn-sm"

onclick="viewBooking('${booking._id}')">

<i class="fa fa-eye"></i>

</button>

<button

class="btn btn-danger btn-sm"

onclick="deleteBooking('${booking._id}')">

<i class="fa fa-trash"></i>

</button>

</td>

</tr>

`;

});

}

async function updateStatus(id,status){

await fetch(API+"/"+id,{

method:"PUT",

headers:{

"Content-Type":"application/json"

},

body:JSON.stringify({

status:status

})

});

loadBookings();

loadStats();

}

async function deleteBooking(id){

if(!confirm("Delete Booking?")) return;

await fetch(API+"/"+id,{

method:"DELETE"

});

loadBookings();

loadStats();

}

async function viewBooking(id){

const res=await fetch(API+"/"+id);

const booking=await res.json();

alert(

"Booking ID : "+booking.bookingId+

"\n\nCustomer : "+booking.customerName+

"\nWorker : "+booking.workerName+

"\nService : "+booking.service+

"\nAmount : ₹"+booking.amount+

"\nAddress : "+booking.address+

"\nStatus : "+booking.status+

"\nBooking Date : "+new Date(booking.createdAt).toLocaleString()

);

}

function searchBooking(){

const key=document.getElementById("searchInput").value.toLowerCase();

const result=bookings.filter(b=>

b.bookingId.toLowerCase().includes(key)||

b.customerName.toLowerCase().includes(key)||

(b.workerName||"").toLowerCase().includes(key)||

b.service.toLowerCase().includes(key)

);

renderTable(result);

}

function filterBooking(){

const status=document.getElementById("statusFilter").value;

if(status==""){

renderTable(bookings);

return;

}

renderTable(

bookings.filter(b=>b.status===status)

);

}