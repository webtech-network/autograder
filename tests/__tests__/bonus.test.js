const axios = require('axios');
const cheerio = require('cheerio');
const { BASE_URL } = require('../config');

const axiosNoRedirect = axios.create({
    maxRedirects: 0,
    validateStatus: function (status) {
        return status >= 200 && status < 500;
    }
});

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
    
    test('student used PRG correctly', async () => {
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
        expect(response.headers.location).toBe('/contato-recebido');
    });

    test('student handled 404 status code', async () => {
        const response = await axiosNoRedirect.get(`${BASE_URL}/random-url`);
    
        expect(response.status).toBe(404);

        const contentType = response.headers['content-type'];
        expect(contentType).toMatch(/html/);

        const $ = cheerio.load(response.data);
        const rootLink = $('a[href="/"]');
        expect(rootLink.length).toBeGreaterThan(0);
    });

    test("student used correct labels for the root route's form", async () => {
        const response = await axios.get(`${BASE_URL}`);
        const $ = cheerio.load(response.data);
        const requiredFields = ['nome', 'ingredientes'];

        checkLabelsForForm($, requiredFields);
    });

    test("student used correct labels for the /contato route's form", async () => {
        const response = await axios.get(`${BASE_URL}/contato`);
        const $ = cheerio.load(response.data);
        const requiredFields = ['nome', 'email', 'assunto', 'mensagem'];

        checkLabelsForForm($, requiredFields);
    });

});