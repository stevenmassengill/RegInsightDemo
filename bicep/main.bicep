param prefix string = 'RegInsightDemo'
param location string = 'eastus'

/* 
  The resource group must be created at the subscription scope.
  Remove this resource and create the resource group before deploying this Bicep file,
  or use a separate Bicep file/module at the subscription scope to create it.
*/

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
  // Storage account names must be between 3 and 24 characters, lowercase, and unique
  name: toLower('${prefix}sa${uniqueString(resourceGroup().id)}')
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true
  }
}

resource pur 'Microsoft.Purview/accounts@2021-07-01' = {
  name: '${prefix}purview'
  location: location
  properties: {}
}

output searchEndpoint string = 'https://${search.name}.search.windows.net'
