import {
  navbar,
  navbarLogo,
  navPillBase,
  navPillActive,
  logoutButton
} from '../styles/theme'

const DEFAULT_TABS = [
  { key: "todos-cursos", label: "Todos os Cursos" },
  { key: "meus-cursos", label: "Meus Cursos" },
  { key: "conta", label: "Conta" }
]

function Navbar({ activeTab, onTabChange, onLogout, logoUrl, tabLabels }) {
  const tabs = DEFAULT_TABS.map(tab => ({
    ...tab,
    label: tabLabels?.[tab.key] || tab.label
  }))

  return (
    <nav style={navbar}>
      <img
        src={logoUrl || "/logo-iaclube.png"}
        alt="Logo"
        style={navbarLogo}
      />

      <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
        {tabs.map(tab => (
          <button
            key={tab.key}
            type="button"
            onClick={() => onTabChange(tab.key)}
            style={activeTab === tab.key ? navPillActive : navPillBase}
          >
            {tab.label}
          </button>
        ))}

        <button
          type="button"
          onClick={onLogout}
          style={logoutButton}
          title="Sair"
          aria-label="Sair"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>
    </nav>
  )
}

export default Navbar