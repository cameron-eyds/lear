<template>
  <v-expansion-panels accordion multiple :value=[0]>
    <!-- Registered Office -->
    <v-expansion-panel class="align-items-top address-panel">
      <v-expansion-panel-header class="panel-header-btn">
        <div class="list-item__title">Registered Office</div>
      </v-expansion-panel-header>
      <v-expansion-panel-content class="panel-wrapper">
        <v-list class="pt-0 pb-0">

          <v-list-item v-if="deliveryAddress">
            <v-list-item-icon class="address-icon mr-0">
              <v-icon color="primary">mdi-truck</v-icon>
            </v-list-item-icon>
            <v-list-item-content>
              <v-list-item-title class="mb-2">Delivery Address</v-list-item-title>
              <v-list-item-subtitle>
                <ul class="address-info">
                  <li>{{ deliveryAddress.streetAddress }}</li>
                  <li>{{ deliveryAddress.addressCity }} {{ deliveryAddress.addressRegion }}
                    &nbsp;&nbsp;{{ deliveryAddress.postalCode}}</li>
                  <li>{{ deliveryAddress.addressCountry }}</li>
                </ul>
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>

          <v-list-item v-if="mailingAddress">
            <v-list-item-icon class="address-icon mr-0">
              <v-icon color="primary">mdi-email-outline</v-icon>
            </v-list-item-icon>
            <v-list-item-content>
              <v-list-item-title class="mb-2">Mailing Address</v-list-item-title>
              <v-list-item-subtitle>
                <div v-if="isSameAddress(deliveryAddress, mailingAddress)">
                  Same as above
                </div>
                <ul class="address-info" v-else>
                  <li>{{ mailingAddress.streetAddress }}</li>
                  <li>{{ mailingAddress.addressCity }} {{ mailingAddress.addressRegion }}
                    &nbsp;&nbsp;{{ mailingAddress.postalCode}}</li>
                  <li>{{ mailingAddress.addressCountry }}</li>
                </ul>
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>

        </v-list>
      </v-expansion-panel-content>
    </v-expansion-panel>

    <!-- Records Office -->
    <v-expansion-panel class="align-items-top address-panel" v-if="entityFilter(EntityTypes.BCorp)">
      <v-expansion-panel-header class="panel-header-btn">
        <div class="list-item__title">Record Office</div>
      </v-expansion-panel-header>
      <v-expansion-panel-content class="panel-wrapper">
        <v-list class="pt-0 pb-0">

          <v-list-item v-if="deliveryAddress">
            <v-list-item-icon class="address-icon mr-0">
              <v-icon color="primary">mdi-truck</v-icon>
            </v-list-item-icon>
            <v-list-item-content>
              <v-list-item-title class="mb-2">Delivery Address</v-list-item-title>
              <v-list-item-subtitle>
                <ul class="address-info">
                  <li>{{ deliveryAddress.streetAddress }}</li>
                  <li>{{ deliveryAddress.addressCity }} {{ deliveryAddress.addressRegion }}
                    &nbsp;&nbsp;{{ deliveryAddress.postalCode}}</li>
                  <li>{{ deliveryAddress.addressCountry }}</li>
                </ul>
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>

          <v-list-item v-if="mailingAddress">
            <v-list-item-icon class="address-icon mr-0">
              <v-icon color="primary">mdi-email-outline</v-icon>
            </v-list-item-icon>
            <v-list-item-content>
              <v-list-item-title class="mb-2">Mailing Address</v-list-item-title>
              <v-list-item-subtitle>
                <div v-if="isSameAddress(deliveryAddress, mailingAddress)">
                  Same as above
                </div>
                <ul class="address-info" v-else>
                  <li>{{ mailingAddress.streetAddress }}</li>
                  <li>{{ mailingAddress.addressCity }} {{ mailingAddress.addressRegion }}
                    &nbsp;&nbsp;{{ mailingAddress.postalCode}}</li>
                  <li>{{ mailingAddress.addressCountry }}</li>
                </ul>
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>

        </v-list>
      </v-expansion-panel-content>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script lang="ts">
// Libraries
import { Component, Mixins } from 'vue-property-decorator'
import { mapState } from 'vuex'

// Mixins
import { EntityFilterMixin, AddressMixin } from '@/mixins'

// Enums
import { EntityTypes } from '@/enums'

// Interfaces
import { AddressIF } from '@/interfaces/address-interfaces'

@Component({
  computed: {
    ...mapState(['mailingAddress', 'deliveryAddress'])
  },
  mixins: [EntityFilterMixin, AddressMixin]
})
export default class AddressListSm extends Mixins(EntityFilterMixin, AddressMixin) {
  // Base Address properties
  readonly mailingAddress: AddressIF
  readonly deliveryAddress: AddressIF

  // EntityTypes Enum
  readonly EntityTypes: {} = EntityTypes

  // created () {
  //   console.log(this.deliveryAddress)
  // }
}
</script>

<style lang="scss" scoped>
  @import "../../assets/styles/theme.scss";

  // Variables
  $icon-width: 2.75rem;

  .panel-wrapper {
    margin-left: -1.5rem;
  }
  .panel-header-btn {
    padding-left: .85rem;
  }

  .v-list-item {
    padding: 0 1rem;
  }

  .v-list-item__icon {
    margin-top: 0.7rem;
    margin-right: 0;
  }

  .v-list-item__title {
    font-size: 0.875rem;
    font-weight: 400;
  }

  .address-icon {
     width: $icon-width;
   }

  .address-info {
    margin: 0;
    padding: 0;
    list-style-type: none;
  }
</style>
