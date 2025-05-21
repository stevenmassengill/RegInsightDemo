param prefix string = 'RegInsightDemo'

// Convert prefix to lower case for resources that require lower-case names
var lowerPrefix = toLower(prefix)
param location string = 'eastus'

// Storage account names must be 24 characters or less. We combine a shortened
// prefix, the string 'sa', and a unique string derived from the resource group
// ID. uniqueString() returns a 13-character value, so the prefix portion must
// be no more than 9 characters to stay within the limit.
var saPrefix = toLower(substring(prefix, 0, 9))
// Unique suffix derived from the resource group ensures the storage account
// name remains globally unique while staying within the 24 character limit.
var saSuffix = uniqueString(resourceGroup().id)

/* 
  The resource group must be created at the subscription scope.
  Remove this resource and create the resource group before deploying this Bicep file,
  or use a separate Bicep file/module at the subscription scope to create it.
*/

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: '${lowerPrefix}search'
  location: location
  sku: {
    name: 'standard'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
  }
}

resource openai 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${lowerPrefix}openai'
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {}
}

resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  // Compose the storage account name from the shortened prefix, 'sa', and the
  // deterministic unique suffix. This keeps the name under 24 characters and
  // uses only lower-case letters and numbers.
  name: '${saPrefix}sa${saSuffix}'
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
