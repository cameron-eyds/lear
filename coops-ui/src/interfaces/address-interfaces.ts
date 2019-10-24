import Vue from 'vue'

export interface BaseAddressType extends Vue {
  $refs: any
}

export interface AddressIF extends Vue {
  addressCity: string
  addressCountry: string
  addressRegion: string
  deliveryInstructions?: string
  postalCode: string
  streetAddress: string
  streetAddressAdditional?: string
}
