// This file contains the JavaScript code for the Tienda de Laura website.
// It handles interactivity such as adding items to a shopping cart, filtering products, and managing user interactions.

document.addEventListener('DOMContentLoaded', () => {
    const cart = [];
    const products = [
        { id: 1, name: 'Camiseta', price: 20 },
        { id: 2, name: 'Pantalones', price: 40 },
        { id: 3, name: 'Zapatos', price: 60 },
    ];

    const productContainer = document.getElementById('product-list');
    const cartContainer = document.getElementById('cart');

    function displayProducts() {
        products.forEach(product => {
            const productElement = document.createElement('div');
            productElement.classList.add('product');
            productElement.innerHTML = `
                <h3>${product.name}</h3>
                <p>Precio: $${product.price}</p>
                <button onclick="addToCart(${product.id})">Agregar al carrito</button>
            `;
            productContainer.appendChild(productElement);
        });
    }

    window.addToCart = function(productId) {
        const product = products.find(p => p.id === productId);
        if (product) {
            cart.push(product);
            updateCart();
        }
    };

    function updateCart() {
        cartContainer.innerHTML = '';
        cart.forEach(item => {
            const cartItem = document.createElement('div');
            cartItem.innerHTML = `${item.name} - $${item.price}`;
            cartContainer.appendChild(cartItem);
        });
    }

    displayProducts();
});