import { startAuthentication, startRegistration, platformAuthenticatorIsAvailable } from '@simplewebauthn/browser'
import {
  getWebauthnAuthenticationOptions,
  getWebauthnRegistrationOptions,
  verifyWebauthnAuthentication,
  verifyWebauthnRegistration,
} from '@/lib/api'
import type { AuthStatusResponse } from '@/types/api'

export async function isPlatformAuthenticatorAvailable(): Promise<boolean> {
  try {
    return await platformAuthenticatorIsAvailable()
  } catch {
    return false
  }
}

export async function registerPasskey(deviceLabel?: string): Promise<void> {
  const optionsJSON = await getWebauthnRegistrationOptions()
  const credential = await startRegistration({ optionsJSON })
  await verifyWebauthnRegistration(credential, deviceLabel)
}

export async function authenticateWithPasskey(): Promise<AuthStatusResponse> {
  const optionsJSON = await getWebauthnAuthenticationOptions()
  const credential = await startAuthentication({ optionsJSON })
  return verifyWebauthnAuthentication(credential)
}
