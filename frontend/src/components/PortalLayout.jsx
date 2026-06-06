import { useEffect, useState } from "react";

const CAROUSEL_IMAGES = [
  "https://portal.nycu.edu.tw/img/login-page/bg-1.jpg",
  "https://portal.nycu.edu.tw/img/login-page/bg-2.jpg",
  "https://portal.nycu.edu.tw/img/login-page/bg-3.jpg",
  "https://portal.nycu.edu.tw/img/login-page/bg-4.jpg",
];

export default function PortalLayout({ children }) {
  const [activeSlide, setActiveSlide] = useState(0);

  useEffect(() => {
    if (CAROUSEL_IMAGES.length <= 1) return undefined;
    const timer = setInterval(() => {
      setActiveSlide((index) => (index + 1) % CAROUSEL_IMAGES.length);
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="container">
      <section className="left-half" aria-hidden="true">
        <div className="image-carousel">
          <div className="carousel-container">
            {CAROUSEL_IMAGES.map((url, index) => (
              <div
                key={url}
                className={`carousel-slide${index === activeSlide ? " active" : ""}`}
                style={{ backgroundImage: `url("${url}")` }}
              />
            ))}
            <div className="logo-overlay">
              <div className="logo-container">
                <img
                  className="logo-image"
                  src="https://portal.nycu.edu.tw/img/LogoAndSchoolName.png"
                  alt="NYCU"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="right-half">
        <div className="portal-header">
          <img
            className="nycu-logo"
            src="https://portal.nycu.edu.tw/img/nycu-logo.png"
            alt="NYCU Logo"
          />
          <span>國立陽明交通大學單一入口</span>
        </div>
        <div className="right-content">{children}</div>
      </section>
    </div>
  );
}
