
param prefix string
param location string = 'eastus'

resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: '${prefix}-rg'
  location: location
}

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: '${prefix}search'
  location: location
  sku: {
    name: 'basic'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
  }
}

resource openai 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${prefix}openai'
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {}
}

resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '${prefix}sa'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true
  }
}

resource pur 'Microsoft.Purview/accounts@2023-02-01-preview' = {
  name: '${prefix}purview'
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {}
}

output searchEndpoint string = search.properties.primaryEndpoints.query
