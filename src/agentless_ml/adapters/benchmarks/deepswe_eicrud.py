"""Eicrud's public MongoDB schedule, with candidate-generated clients."""

EICRUD_MONGO_SCRIPT = r'''
set -e
cd /tmp/work || exit 125
export PATH=/app/node_modules/.bin:$PATH NPM_CONFIG_OFFLINE=true
# Keep third-party dependencies from the image, but every local package from
# the candidate. Link dependencies individually so @eicrud stays writable.
for package in . shared cli core client db_mongo db_postgre; do
    mkdir -p "$package/node_modules/@eicrud"
    for entry in /app/$package/node_modules/* /app/$package/node_modules/.[!.]*; do
        [ -e "$entry" ] || continue
        case "${entry##*/}" in @eicrud|.cache|.vite|.vite-temp) continue;; esac
        ln -s "$entry" "$package/node_modules/"
    done
    for mapping in core:core shared:shared client:client cli:cli mongodb:db_mongo postgresql:db_postgre; do
        name=${mapping%%:*}; directory=${mapping#*:}
        ln -s /tmp/work/$directory "$package/node_modules/@eicrud/$name"
        [ "$(readlink -f "$package/node_modules/@eicrud/$name")" = "/tmp/work/$directory" ] || exit 125
    done
done
# Compile the candidate CLI/shared library, not the installed global CLI.
(cd shared && npm run compile) || exit 125
(cd cli && npm run compile) || exit 125
node /tmp/work/cli/commands/index.js export dtos || exit 125
node /tmp/work/cli/commands/index.js export superclient || exit 125
node /tmp/work/cli/commands/index.js export openapi -o-jqs || exit 125
npm run setup:oapi:client || exit 125
[ -f test/oapi-client/sdk.gen.ts ] || exit 125
[ -f test/test_exports/services/superclient-ms/superclient-test/superclient-test.entity.ts ] || exit 125
# Public CI builds after generation, before invoking test:mongo.
npm run build || exit 125
mkdir -p /tmp/eicrud-mongo
mongod --bind_ip 127.0.0.1 --port 27017 --dbpath /tmp/eicrud-mongo \
    --logpath /tmp/eicrud-mongo/mongod.log --pidfilepath /tmp/eicrud-mongo/mongod.pid --fork || exit 125
trap 'kill "$(cat /tmp/eicrud-mongo/mongod.pid)" 2>/dev/null || true' EXIT
node -e 'const {MongoClient}=require("mongodb"); (async()=>{const client=new MongoClient("mongodb://127.0.0.1:27017",{serverSelectionTimeoutMS:5000}); try{await client.connect(); await client.db("admin").command({ping:1}); console.log("local MongoDB ping verified");} finally{await client.close();}})().catch(error=>{console.error(error);process.exit(125);});' || exit 125
rm -rf /tmp/work/ctrf
set +e
# Match test:mongo's database and forceExit flags, replacing its worker count
# once. Appending another maxWorkers makes Jest 30 parse the duplicate as 50.
TEST_CRUD_DB=mongo /app/node_modules/.bin/jest --forceExit --ci --maxWorkers=2 --reporters=default \
    --reporters=/opt/jest-ctrf/node_modules/jest-ctrf-json-reporter/dist/index.js
exit $?
'''.strip()
