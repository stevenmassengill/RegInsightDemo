param prefix string = 'RegInsightDemo'
param location string = 'eastus'

// Storage account names must be 24 characters or less. We combine a shortened
// prefix, the string 'sa', and a unique string derived from the resource group
// ID. uniqueString() returns a 13-character value, so the prefix portion must
// be no more than 9 characters to stay within the limit.
var saPrefix = toLower(substring(prefix, 0, 9))

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
  // Compose the storage account name from the shortened prefix, 'sa', and a
  // deterministic unique string. This ensures the name meets the length and
  // character requirements while remaining unique within Azure.
  name: '${saPrefix}sa${uniqueString(resourceGroup().id)}'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true
  }
}

output searchEndpoint string = 'https://${search.name}.search.windows.net'
