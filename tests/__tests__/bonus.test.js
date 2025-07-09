const axios = require('axios');
const cheerio = require('cheerio');
const { BASE_URL } = require('../config');

const axiosNoRedirect = axios.create({
    maxRedirects: 0,
    validateStatus: function (status) {
        return status >= 200 && status < 500;
    }
});

function safeTest(description, asyncTestFn) {
    test(description, async () => {
        try {
            await asyncTestFn();
        } catch (error) {
            // If the server is down, throw a specific, clean error message.
            if (error.code === 'ECONNREFUSED') {
                throw new Error(`Connection refused during test: "${description}". Is the server running?`);
            }
            // For any other error, re-throw a simplified version to avoid circular structure issues.
            throw new Error(`An unexpected error occurred in test "${description}": ${error.message}`);
        }
    });
}

/**
 * A helper function to check for correctly associated labels and form fields.
 * @param {cheerio.CheerioAPI} $ - The Cheerio instance loaded with the HTML page.
 * @param {string[]} fieldNames - An array of 'name' attributes to check.
 */
function checkLabelsForForm($, fieldNames) {
    for (const name of fieldNames) {
        const $input = $(`[name="${name}"]`);
        
        if ($input.length === 0) {
            throw new Error(`Test failed: Form field with name="${name}" was not found.`);
        }

        const inputId = $input.attr('id');
        
        if (!inputId) {
            throw new Error(`Test failed: Form field with name="${name}" is missing an 'id' attribute.`);
        }

        const $label = $(`label[for="${inputId}"]`);
        
        if ($label.length === 0) {
            throw new Error(`Test failed: A <label> with the attribute for="${inputId}" was not found.`);
        }
    }
}

describe('Bonus Tests - ', () => {

    safeTest('estudante utilizou padrão PRG na rota /contato corretamente (Stateless)', async () => {
        const contactSubmission = {
            nome: "Tram Anh Nguyen",
            email: "tramanh@gmail.com",
            assunto: "Testing PRG",
            mensagem: "This is a test for the Post-Redirect-Get pattern."
        };
        
        const response = await axiosNoRedirect.post(`${BASE_URL}/contato`, contactSubmission, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });

        expect(response.status).toBeGreaterThanOrEqual(300);
        expect(response.status).toBeLessThan(400);

        const locationHeader = response.headers.get('Location');
        expect(locationHeader).toBeDefined();

        const redirectURL = new URL(locationHeader, BASE_URL);
        expect(redirectURL.pathname).toBe('/contato-recebido');

        for (const [key, value] of Object.entries(contactSubmission)) {
            expect(redirectURL.searchParams.get(key)).toBe(value);
        }
    })

    safeTest('estudante criou template exibido em requisições 404 contendo uma âncora para a rota raíz', async () => {
        const response = await axiosNoRedirect.get(`${BASE_URL}/random-url`);
    
        expect(response.status).toBe(404);

        const contentType = response.headers['content-type'];
        expect(contentType).toMatch(/html/);

        const $ = cheerio.load(response.data);
        const rootLink = $('a[href="/"]');
        expect(rootLink.length).toBeGreaterThan(0);
    });

    safeTest("estudante utilizou corretamente as tags label e attributo id nos inputs 'nome' e 'ingredientes' na rota /sugestao", async () => {
        const response = await axios.get(`${BASE_URL}`);
        const $ = cheerio.load(response.data);
        const requiredFields = ['nome', 'ingredientes'];

        checkLabelsForForm($, requiredFields);
    });

    safeTest("estudante utilizou corretamente as tags label e attributo id nos inputs 'nome', 'email', 'assunto' and 'mensagem' do fomulário da rota /contato (GET)", async () => {
        const response = await axios.get(`${BASE_URL}/contato`);
        const $ = cheerio.load(response.data);
        const requiredFields = ['nome', 'email', 'assunto', 'mensagem'];

        checkLabelsForForm($, requiredFields);
    });

});