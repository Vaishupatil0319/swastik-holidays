// Booking Chart
const bookingCtx = document.getElementById('bookingChart');

if (bookingCtx) {
 new Chart(bookingCtx, {
    type: 'bar',

    data: {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        datasets: [{
            label: 'Bookings',
            data: [5, 8, 12, 9, 15, 20],
            backgroundColor: '#0d6efd'
        }]
    },

    options: {
        responsive: true,
        maintainAspectRatio: false
    }
});
}

// Revenue Chart
const revenueCtx = document.getElementById('revenueChart');

if (revenueCtx) {
new Chart(revenueCtx, {
    type: 'line',

    data: {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        datasets: [{
            label: 'Revenue',
            data: [12000, 18000, 25000, 21000, 30000, 42000],
            borderColor: '#198754',
            backgroundColor: 'rgba(25,135,84,0.2)',
            fill: true,
            tension: 0.4
        }]
    },

    options: {
        responsive: true,
        maintainAspectRatio: false
    }
});
}