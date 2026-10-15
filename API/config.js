/**
 * E-commerce Application Configuration
 * 
 * Customize your store information and external API endpoint here.
 * When a customer checks out, the order payload will be sent to `ORDER_API_ENDPOINT`.
 */
const CONFIG = {
  // Store details
  storeName: "NovaStore",
  currency: "$",
  currencyCode: "USD",
  taxRate: 0.08, // 8% sales tax
  shippingFee: 15.00,
  freeShippingThreshold: 100.00,

  // External Order API Configuration
  // This will check if you saved an IP in the UI modal, otherwise uses default
  ORDER_API_ENDPOINT: localStorage.getItem("novastore_api_endpoint") || "http://10.195.66.58:5000/api/orders",
  
  // Headers to include in the order forwarding request
  API_HEADERS: {
    "Content-Type": "application/json",
  },

  // Toggle fallback / simulation if external API fails or is not yet live
  ALLOW_OFFLINE_SIMULATION: true,
};

// Products Catalog
const INITIAL_PRODUCTS = [
  {
    id: "prod-oven",
    name: "Oven",
    category: "Appliances",
    price: 199.99,
    originalPrice: 249.99,
    rating: 4.8,
    reviewsCount: 154,
    badge: "Popular",
    image: "https://images.unsplash.com/photo-1574269909862-7e1d70bb8078?auto=format&fit=crop&w=800&q=80",
    description: "Multifunctional convection oven with digital touch panel, auto-cook menus, and rapid grill defrost mode."
  },
  {
    id: "prod-fan",
    name: "Table Fan",
    category: "Appliances",
    price: 49.99,
    originalPrice: 65.00,
    rating: 4.6,
    reviewsCount: 89,
    badge: "Trending",
    image: "https://images.unsplash.com/photo-1618941716939-553df3c6c278?auto=format&fit=crop&w=800&q=80",
    description: "Whisper-quiet brushless DC motor with 3 speed modes, aerodynamic blades, and 90-degree oscillation."
  },
  {
    id: "prod-cycle",
    name: "Cycle",
    category: "Outdoors & Fitness",
    price: 349.00,
    originalPrice: 420.00,
    rating: 4.9,
    reviewsCount: 215,
    badge: "Best Seller",
    image: "https://images.unsplash.com/photo-1485965120184-e220f721d03e?auto=format&fit=crop&w=800&q=80",
    description: "Lightweight aircraft aluminum frame, 21-speed Shimano transmission gear system, and dual hydraulic disc brakes."
  },
  {
    id: "prod-chair",
    name: "Chair",
    category: "Furniture",
    price: 179.50,
    originalPrice: 219.00,
    rating: 4.8,
    reviewsCount: 180,
    badge: "Top Rated",
    image: "https://images.unsplash.com/photo-1580481077195-c3f990f23bcb?auto=format&fit=crop&w=800&q=80",
    description: "Breathable back mesh, 3D adjustable armrests, synchronized tilt mechanism, and heavy-duty nylon base."
  },
  {
    id: "prod-sofa",
    name: "Sofa",
    category: "Furniture",
    price: 649.00,
    originalPrice: 799.00,
    rating: 4.7,
    reviewsCount: 92,
    badge: "Premium",
    image: "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=800&q=80",
    description: "High-density resilience foam cushioning, stain-resistant velvet upholstery, and tapered solid oak wood legs."
  },
  {
    id: "prod-table",
    name: "Table",
    category: "Furniture",
    price: 299.00,
    originalPrice: 350.00,
    rating: 4.8,
    reviewsCount: 110,
    badge: "",
    image: "https://images.unsplash.com/photo-1533090161767-e6ffed986c88?auto=format&fit=crop&w=800&q=80",
    description: "Crafted from sustainable solid oak timber with scratch-proof matte protective coating and reinforced frame."
  },
  {
    id: "prod-cooker",
    name: "Cooker",
    category: "Kitchen",
    price: 89.99,
    originalPrice: 115.00,
    rating: 4.9,
    reviewsCount: 260,
    badge: "Best Seller",
    image: "https://images.unsplash.com/photo-1544233726-9f1d2b27be8b?auto=format&fit=crop&w=800&q=80",
    description: "10-in-1 programmable appliance: pressure cooker, slow cooker, rice cooker, steamer, sauté pan, and yogurt maker."
  },
  {
    id: "prod-ac",
    name: "AC",
    category: "Appliances",
    price: 529.00,
    originalPrice: 620.00,
    rating: 4.7,
    reviewsCount: 145,
    badge: "Energy Saver",
    image: "https://images.unsplash.com/photo-1628744448840-55bdb2497bd4?auto=format&fit=crop&w=800&q=80",
    description: "5-star energy rated twin-rotary inverter compressor with fast-cool turbo mode and PM 2.5 air purification filter."
  },
  {
    id: "prod-wm",
    name: "Washing Machine",
    category: "Appliances",
    price: 479.00,
    originalPrice: 560.00,
    rating: 4.8,
    reviewsCount: 172,
    badge: "",
    image: "https://images.unsplash.com/photo-1626806787461-102c1bfaaea1?auto=format&fit=crop&w=800&q=80",
    description: "8kg capacity, direct drive motor with steam hygiene cycle, 14 specialized fabric programs, and smart diagnosis."
  },
  {
    id: "prod-tv",
    name: "TV",
    category: "Electronics",
    price: 799.00,
    originalPrice: 999.00,
    rating: 4.9,
    reviewsCount: 340,
    badge: "Top Choice",
    image: "https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?auto=format&fit=crop&w=800&q=80",
    description: "Self-lit OLED pixels with Dolby Vision HDR, Dolby Atmos surround sound, and integrated smart streaming platforms."
  },
  {
    id: "prod-drone",
    name: "Drone",
    category: "Electronics",
    price: 389.00,
    originalPrice: 470.00,
    rating: 4.8,
    reviewsCount: 198,
    badge: "Hot",
    image: "https://images.unsplash.com/photo-1527977966376-1c8408f9f108?auto=format&fit=crop&w=800&q=80",
    description: "3-axis mechanical gimbal with 4K HDR camera, 35-minute flight time, obstacle sensing, and intelligent return-to-home."
  },
  {
    id: "prod-stabiliser",
    name: "Stabiliser",
    category: "Appliances",
    price: 65.00,
    originalPrice: 85.00,
    rating: 4.7,
    reviewsCount: 84,
    badge: "Protection",
    image: "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=800&q=80",
    description: "Advanced microcontroller-based voltage stabilizer with high/low voltage cut-off and digital display monitoring."
  }
];
