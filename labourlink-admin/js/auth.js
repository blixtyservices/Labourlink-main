const form = document.getElementById("loginForm");

form.addEventListener("submit", async (e) => {

    e.preventDefault();

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    const res = await fetch(API + "/admin/login", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            email,
            password
        })
    });

    const data = await res.json();

    if (res.ok) {

        // Save JWT token
        localStorage.setItem("token", data.token);

        // Save admin details
        localStorage.setItem("admin", JSON.stringify(data.admin));

        location.href = "dashboard.html";

    } else {

        alert(data.detail || "Invalid Credentials");

    }

});