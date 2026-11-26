const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'../src/main/resources/META-INF/resources/vendor');
fs.mkdirSync(root,{recursive:true});
fs.copyFileSync(path.join(__dirname,'node_modules/@redhat/keycloak-js/lib/keycloak.js'),path.join(root,'keycloak.js'));
fs.copyFileSync(path.join(__dirname,'node_modules/@redhat/keycloak-js/LICENSE.txt'),path.join(root,'keycloak-LICENSE.txt'));
