/* Context modules pair Provider + hook; fast-refresh wants single export. */
/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, type ReactNode } from 'react'

export type CustomerSession =
  | { mode: 'disabled' }
  | {
      mode: 'auth0'
      isLoading: boolean
      isAuthenticated: boolean
      login: () => void
      logout: () => void
      userEmail: string | undefined
    }

const CustomerSessionContext = createContext<CustomerSession>({ mode: 'disabled' })

export function CustomerSessionProvider({
  value,
  children,
}: {
  value: CustomerSession
  children: ReactNode
}) {
  return <CustomerSessionContext.Provider value={value}>{children}</CustomerSessionContext.Provider>
}

export function useCustomerSession(): CustomerSession {
  return useContext(CustomerSessionContext)
}
