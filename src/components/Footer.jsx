const wrapperStyle = {
  marginTop: "40px",
  padding: "20px 32px",
  background: "var(--lms-navy, #152A47)",
  borderRadius: "16px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "36px",
  flexWrap: "wrap"
}

const labelStyle = {
  color: "rgba(255,255,255,0.8)",
  fontSize: "12px",
  marginRight: "8px"
}

const logoStyle = {
  height: "32px",
  objectFit: "contain"
}

function Footer() {
  return (
    <div style={wrapperStyle}>
      <span style={labelStyle}>Apoio</span>
      <img src="/footer-ccom.png" alt="CCOM" style={logoStyle} />
      <img src="/footer-nmi.png" alt="RNP" style={logoStyle} />
      <img src="/footer-unb.png" alt="UnB" style={logoStyle} />
    </div>
  )
}

export default Footer
