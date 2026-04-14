import { Component } from 'react'
import { Link } from 'react-router-dom'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    // Garder une trace dans la console pour debug.
    console.error('UI crashed:', error)
    console.error('Component stack:', errorInfo?.componentStack)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    const details = import.meta.env.DEV
      ? (this.state.error?.message || String(this.state.error))
      : null

    return (
      <div className="space-y-3 py-6">
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          ❌ Une erreur est survenue dans l’interface.
          {details ? (
            <div className="mt-2 text-red-700/90">
              Détails (DEV): {details}
            </div>
          ) : null}
        </div>
        <Link
          to="/"
          className="inline-flex items-center rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
        >
          ← Retour au tableau de bord
        </Link>
      </div>
    )
  }
}

export default ErrorBoundary
