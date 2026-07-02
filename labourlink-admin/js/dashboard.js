const API = "http://172.20.10.3:8000/api";

async function loadDashboard() {
    try {
        const res = await fetch(API + "/admin/dashboard");
        const data = await res.json();

        console.log(data);

        document.getElementById("usersCount").innerHTML = data.total_users;
        document.getElementById("workerCount").innerHTML = data.total_workers;
        document.getElementById("bookingCount").innerHTML = data.total_bookings;
        document.getElementById("revenue").innerHTML = "₹0";

    } catch (e) {
        console.error(e);
    }
}

loadDashboard();    