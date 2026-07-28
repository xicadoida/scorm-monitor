export const colors = {
  navy: "#152A47",
  orange: "#EF4923",
  orangeHover: "#D63F1A",
  yellow: "#F2B134",
  white: "#FFFFFF",
  pageBackground: "#EEF1F6",
  textMuted: "#94A3B8",
  errorText: "#FF6B6B",
  successText: "#7CD992"
}

export const pageWrapper = {
  minHeight: "100vh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: colors.pageBackground,
  fontFamily: "'Segoe UI', Arial, sans-serif"
}

export const card = {
  background: colors.navy,
  borderRadius: "24px",
  padding: "36px 32px",
  width: "360px",
  boxSizing: "border-box",
  boxShadow: "0 20px 40px rgba(0,0,0,0.25)"
}

export const logo = {
  display: "block",
  margin: "0 auto 24px auto",
  height: "56px"
}

export const input = {
  width: "100%",
  padding: "14px 18px",
  borderRadius: "999px",
  border: "none",
  outline: "none",
  fontSize: "15px",
  color: "#1F2937",
  marginBottom: "16px",
  boxSizing: "border-box",
  fontFamily: "inherit"
}

export const linkText = {
  display: "block",
  textAlign: "right",
  color: colors.yellow,
  fontSize: "13px",
  textDecoration: "underline",
  marginBottom: "20px",
  cursor: "pointer",
  background: "none",
  border: "none",
  padding: 0,
  width: "100%"
}

export const buttonRow = {
  display: "flex",
  justifyContent: "flex-end",
  gap: "10px"
}

export const buttonPrimary = {
  padding: "12px 26px",
  borderRadius: "999px",
  border: "none",
  background: colors.orange,
  color: colors.white,
  fontWeight: "bold",
  fontSize: "14px",
  cursor: "pointer"
}

export const buttonOutline = {
  padding: "12px 26px",
  borderRadius: "999px",
  border: `1.5px solid ${colors.white}`,
  background: "transparent",
  color: colors.white,
  fontWeight: "bold",
  fontSize: "14px",
  cursor: "pointer"
}

export const errorMessage = {
  color: colors.errorText,
  fontSize: "13px",
  marginBottom: "12px"
}

export const successMessage = {
  color: colors.successText,
  fontSize: "13px",
  marginBottom: "12px"
}

// ---- Navbar ----

export const navbar = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  background: colors.navy,
  borderRadius: "999px",
  padding: "10px 24px",
  marginBottom: "32px",
  flexWrap: "wrap",
  gap: "12px"
}

export const navbarLogo = {
  height: "38px"
}

export const navPillBase = {
  padding: "10px 20px",
  borderRadius: "999px",
  fontSize: "14px",
  fontWeight: "bold",
  cursor: "pointer",
  border: `1.5px solid ${colors.white}`,
  background: "transparent",
  color: colors.white,
  whiteSpace: "nowrap"
}

export const navPillActive = {
  ...navPillBase,
  background: colors.orange,
  border: `1.5px solid ${colors.orange}`
}

export const logoutButton = {
  background: "transparent",
  border: "none",
  cursor: "pointer",
  padding: "8px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center"
}

// ---- Página / seções ----

export const pageBackground = {
  minHeight: "100vh",
  background: colors.pageBackground,
  padding: "32px",
  fontFamily: "'Segoe UI', Arial, sans-serif"
}

export const sectionTitle = {
  color: colors.orange,
  fontSize: "18px",
  fontWeight: "bold",
  marginBottom: "16px"
}

export const searchInput = {
  padding: "12px 20px",
  borderRadius: "999px",
  border: "1px solid #d1d5db",
  fontSize: "14px",
  outline: "none",
  width: "260px",
  boxSizing: "border-box"
}

// ---- Cards de curso ----

export const courseGrid = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
  gap: "20px",
  marginBottom: "32px"
}

export const courseCard = {
  background: colors.navy,
  borderRadius: "16px",
  padding: "20px",
  display: "flex",
  flexDirection: "column",
  gap: "10px",
  minHeight: "110px"
}

export const courseCardHeader = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "10px"
}

export const courseCardTitle = {
  color: colors.white,
  fontSize: "16px",
  fontWeight: "bold",
  margin: 0
}

export const courseCardSubtitle = {
  color: "#B9C2D0",
  fontSize: "13px",
  margin: 0
}

export const coursePillButton = {
  padding: "8px 18px",
  borderRadius: "999px",
  border: "none",
  background: colors.orange,
  color: colors.white,
  fontWeight: "bold",
  fontSize: "13px",
  cursor: "pointer",
  whiteSpace: "nowrap"
}

export const progressWrapper = {
  marginTop: "auto"
}

export const progressPercentLabel = {
  textAlign: "right",
  color: colors.white,
  fontSize: "12px",
  marginBottom: "4px"
}

export const progressTrack = {
  width: "100%",
  height: "6px",
  borderRadius: "999px",
  background: "rgba(255,255,255,0.2)",
  overflow: "hidden"
}

export const progressFill = (percent) => ({
  width: `${percent}%`,
  height: "100%",
  background: colors.yellow,
  borderRadius: "999px"
})

export const emptyStateText = {
  color: colors.textMuted,
  fontSize: "14px"
}

// ---- Paginação ----

export const paginationWrapper = {
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  gap: "8px",
  marginTop: "12px"
}

export const paginationButton = {
  width: "32px",
  height: "32px",
  borderRadius: "999px",
  border: "1px solid #d1d5db",
  background: colors.white,
  color: "#374151",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: "bold"
}

export const paginationButtonActive = {
  ...paginationButton,
  background: colors.orange,
  border: `1px solid ${colors.orange}`,
  color: colors.white
}

export const paginationArrow = {
  ...paginationButton,
  background: "transparent",
  border: "none",
  fontSize: "16px"
}

// ---- Conta ----

export const accountCard = {
  background: colors.navy,
  borderRadius: "16px",
  padding: "24px",
  color: colors.white,
  marginBottom: "32px",
  maxWidth: "420px"
}