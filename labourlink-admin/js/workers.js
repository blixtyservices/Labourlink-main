const API = "http://172.20.10.3:8000/api";

let workers = [];
let filteredWorkers = [];

const table = document.getElementById("workerTable");
const searchInput = document.getElementById("searchWorker");
const categoryFilter = document.getElementById("categoryFilter");

function badge(status) {

    if (status === "verified")
        return '<span class="badge bg-success">Verified</span>';

    if (status === "pending")
        return '<span class="badge bg-warning text-dark">Pending</span>';

    return '<span class="badge bg-secondary">Available</span>';
}

async function loadWorkers() {

    try {

        const res = await fetch(`${API}/workers`);

        if (!res.ok) {
            throw new Error("Unable to load workers");
        }

        workers = await res.json();

        filteredWorkers = [...workers];

        render(filteredWorkers);

    } catch (err) {

        console.error(err);

        table.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-danger">
                    Failed to load workers
                </td>
            </tr>
        `;

    }

}

function render(data) {

    table.innerHTML = "";

    data.forEach(worker => {

        table.innerHTML += `
            <tr>

                <td>
                    <img
                        src="${worker.profile_pic || 'assets/avatar.png'}"
                        style="width:55px;height:55px;border-radius:50%;object-fit:cover;">
                </td>

                <td>${worker.name}</td>

                <td>${worker.category}</td>

                <td>${worker.city}</td>

                <td>⭐ ${worker.rating}</td>

                <td>${badge(worker.status)}</td>

                <td>

                    <button class="btn btn-success btn-sm">
                        <i class="fa fa-eye"></i>
                    </button>

                    <button class="btn btn-primary btn-sm">
                        <i class="fa fa-pen"></i>
                    </button>

                    <button class="btn btn-danger btn-sm">
                        <i class="fa fa-trash"></i>
                    </button>

                </td>

            </tr>
        `;

    });

}

searchInput.addEventListener("keyup", function () {

    const value = this.value.toLowerCase();

    filteredWorkers = workers.filter(worker =>
        worker.name.toLowerCase().includes(value)
    );

    render(filteredWorkers);

});

categoryFilter.addEventListener("change", function () {

    if (this.value === "") {

        render(workers);

        return;
    }

    filteredWorkers = workers.filter(worker =>
        worker.category === this.value
    );

    render(filteredWorkers);

});

loadWorkers();